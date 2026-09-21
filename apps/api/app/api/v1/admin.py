import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.db.session import get_db
from app.domains.administration.models import FeatureFlag, OperatingHour
from app.domains.administration.schemas import (
    AuditEventRead,
    FeatureFlagPatch,
    FeatureFlagRead,
    OperatingHourRead,
    OperatingHourWrite,
)
from app.domains.auth.dependencies import require_roles
from app.domains.auth.models import User, UserRole
from app.domains.common.outbox import AuditLog
from app.domains.workforce.models import Vendor
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
