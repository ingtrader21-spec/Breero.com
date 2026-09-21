import secrets
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.db.session import get_db
from app.domains.administration.models import FeatureFlag, OperatingHour
from app.domains.administration.schemas import (
    AdminUserCreate,
    AdminUserRead,
    AuditEventRead,
    FeatureFlagPatch,
    FeatureFlagRead,
    OperatingHourRead,
    OperatingHourWrite,
    ProviderApplicationDecision,
)
from app.domains.auth.dependencies import require_roles
from app.domains.auth.models import User, UserRole
from app.domains.auth.repository import UserRepository
from app.domains.auth.security import hash_password
from app.domains.common.outbox import AuditLog
from app.domains.workforce.models import Vendor, VendorStatus, Worker, WorkerStatus
from app.domains.workforce.provider_models import ProviderService, ProviderServiceArea
from app.domains.workforce.schemas import VendorRead

router = APIRouter()
admin_only = require_roles(UserRole.BREERO_ADMIN)
internal_read = require_roles(
    UserRole.BREERO_ADMIN, UserRole.BREERO_DISPATCH, UserRole.BREERO_SUPPORT
)

PROTECTED_FLAGS = {
    "AUTO_ASSIGN_PROVIDER",
    "AUTO_CONFIRM_BOOKING",
    "PAYMENTS_ENABLED",
    "LIVE_PROVIDER_DISPATCH",
    "LIVE_EMAIL_DELIVERY",
    "LIVE_SMS_DELIVERY",
    "LIVE_CALLBACKS",
    "ODOO_DELIVERY_ENABLED",
    "ODOO_WRITE_ENABLED",
}


def audit(actor: User, action: str, resource_type: str, resource_id: uuid.UUID, metadata: dict) -> AuditLog:
    return AuditLog(
        actor_id=actor.id,
        actor_type="user",
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata_json=metadata,
        created_at=datetime.now(UTC),
    )


@router.post("/users", response_model=AdminUserRead, status_code=201)
async def create_admin_user(
    data: AdminUserCreate,
    actor: Annotated[User, Depends(admin_only)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    email = str(data.email).lower()
    if await UserRepository(session).by_email(email):
        raise DomainError("CONFLICT", "An account with this email already exists", 409)
    user = User(
        email=email,
        phone=data.phone,
        full_name=data.full_name.strip(),
        role=data.role,
        password_hash=hash_password(secrets.token_urlsafe(48)),
        password_set_required=True,
        email_verified=False,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise DomainError("CONFLICT", "An account with this email already exists", 409) from exc
    session.add(audit(actor, "admin_user.created", "user", user.id, {"role": user.role.value}))
    await session.commit()
    await session.refresh(user)
    return user


@router.get("/providers", response_model=list[VendorRead])
async def providers(
    _: Annotated[User, Depends(internal_read)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[Vendor]:
    return list((await session.scalars(select(Vendor).order_by(Vendor.created_at.desc()).limit(200))).all())


@router.get("/providers/{provider_id}", response_model=VendorRead)
async def provider(
    provider_id: uuid.UUID,
    _: Annotated[User, Depends(internal_read)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Vendor:
    record = await session.get(Vendor, provider_id)
    if not record:
        raise DomainError("NOT_FOUND", "Provider not found", 404)
    return record


@router.get("/provider-applications", response_model=list[VendorRead])
async def provider_applications(
    _: Annotated[User, Depends(internal_read)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[Vendor]:
    return list(
        (
            await session.scalars(
                select(Vendor)
                .where(Vendor.onboarding_status.in_(["PENDING", "UNDER_REVIEW", "INFORMATION_REQUESTED"]))
                .order_by(Vendor.created_at)
            )
        ).all()
    )


@router.get("/provider-applications/{provider_id}", response_model=VendorRead)
async def provider_application(
    provider_id: uuid.UUID,
    _: Annotated[User, Depends(internal_read)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Vendor:
    return await provider(provider_id, _, session)


async def decide_provider(
    provider_id: uuid.UUID,
    data: ProviderApplicationDecision,
    actor: User,
    session: AsyncSession,
    decision: str,
) -> Vendor:
    record = await session.scalar(select(Vendor).where(Vendor.id == provider_id).with_for_update())
    if not record:
        raise DomainError("NOT_FOUND", "Provider application not found", 404)
    if record.onboarding_status not in {"PENDING", "UNDER_REVIEW", "INFORMATION_REQUESTED"}:
        raise DomainError("INVALID_STATE_TRANSITION", "Provider application is already decided", 409)
    if decision == "APPROVED":
        record.status = VendorStatus.ACTIVE
        record.onboarding_status = "APPROVED"
        record.compliance_status = "APPROVED"
        workers = list((await session.scalars(select(Worker).where(Worker.vendor_id == record.id))).all())
        for worker in workers:
            worker.status = WorkerStatus.ACTIVE
            worker.available = True
        for service in (await session.scalars(select(ProviderService).where(ProviderService.provider_id == record.id))).all():
            service.active = True
            service.approval_status = "APPROVED"
        for area in (await session.scalars(select(ProviderServiceArea).where(ProviderServiceArea.provider_id == record.id))).all():
            area.active = True
            area.approval_status = "APPROVED"
    elif decision == "REJECTED":
        record.status = VendorStatus.REJECTED
        record.onboarding_status = "REJECTED"
    else:
        record.status = VendorStatus.UNDER_REVIEW
        record.onboarding_status = "INFORMATION_REQUESTED"
    session.add(audit(actor, f"provider_application.{decision.lower()}", "vendor", record.id, {"reason": data.reason}))
    await session.commit()
    await session.refresh(record)
    return record


@router.post("/provider-applications/{provider_id}/approve", response_model=VendorRead)
async def approve_provider(
    provider_id: uuid.UUID,
    data: ProviderApplicationDecision,
    actor: Annotated[User, Depends(admin_only)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Vendor:
    return await decide_provider(provider_id, data, actor, session, "APPROVED")


@router.post("/provider-applications/{provider_id}/reject", response_model=VendorRead)
async def reject_provider(
    provider_id: uuid.UUID,
    data: ProviderApplicationDecision,
    actor: Annotated[User, Depends(admin_only)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Vendor:
    return await decide_provider(provider_id, data, actor, session, "REJECTED")


@router.post("/provider-applications/{provider_id}/request-information", response_model=VendorRead)
async def request_provider_information(
    provider_id: uuid.UUID,
    data: ProviderApplicationDecision,
    actor: Annotated[User, Depends(admin_only)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Vendor:
    return await decide_provider(provider_id, data, actor, session, "INFORMATION_REQUESTED")


@router.get("/feature-flags", response_model=list[FeatureFlagRead])
async def feature_flags(
    _: Annotated[User, Depends(internal_read)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[FeatureFlag]:
    return list((await session.scalars(select(FeatureFlag).order_by(FeatureFlag.key))).all())


@router.patch("/feature-flags/{flag}", response_model=FeatureFlagRead)
async def patch_feature_flag(
    flag: str,
    data: FeatureFlagPatch,
    actor: Annotated[User, Depends(admin_only)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> FeatureFlag:
    if flag not in PROTECTED_FLAGS:
        raise DomainError("NOT_FOUND", "Feature flag not found", 404)
    if data.enabled:
        raise DomainError("FORBIDDEN", "Protected production side effects cannot be enabled by API", 403)
    record = await session.get(FeatureFlag, flag)
    if not record:
        raise DomainError("NOT_FOUND", "Feature flag not found", 404)
    record.enabled = False
    record.updated_by = actor.id
    record.updated_at = datetime.now(UTC)
    session.add(audit(actor, "feature_flag.changed", "feature_flag", uuid.uuid5(uuid.NAMESPACE_URL, flag), {"flag": flag, "enabled": False, "reason": data.reason}))
    await session.commit()
    await session.refresh(record)
    return record


@router.get("/operating-hours", response_model=list[OperatingHourRead])
async def operating_hours(
    _: Annotated[User, Depends(internal_read)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[OperatingHour]:
    return list((await session.scalars(select(OperatingHour).order_by(OperatingHour.day_of_week))).all())


@router.put("/operating-hours", response_model=list[OperatingHourRead])
async def replace_operating_hours(
    data: list[OperatingHourWrite],
    actor: Annotated[User, Depends(admin_only)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[OperatingHour]:
    if {item.day_of_week for item in data} != set(range(7)) or len(data) != 7:
        raise DomainError("VALIDATION_ERROR", "Exactly one rule is required for every day", 422)
    for item in data:
        record = await session.get(OperatingHour, item.day_of_week)
        if not record:
            record = OperatingHour(day_of_week=item.day_of_week)
            session.add(record)
        record.start_local_time = item.start_local_time
        record.end_local_time = item.end_local_time
        record.emergency_only = item.emergency_only
        record.active = item.active
        record.updated_by = actor.id
    event_id = uuid.uuid4()
    session.add(audit(actor, "operating_hours.changed", "operating_hours", event_id, {"days": 7}))
    await session.commit()
    return list((await session.scalars(select(OperatingHour).order_by(OperatingHour.day_of_week))).all())


@router.get("/audit-events", response_model=list[AuditEventRead])
async def audit_events(
    _: Annotated[User, Depends(internal_read)],
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[AuditLog]:
    return list((await session.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit))).all())


@router.get("/audit-events/{event_id}", response_model=AuditEventRead)
async def audit_event(
    event_id: uuid.UUID,
    _: Annotated[User, Depends(internal_read)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AuditLog:
    record = await session.get(AuditLog, event_id)
    if not record:
        raise DomainError("NOT_FOUND", "Audit event not found", 404)
    return record
