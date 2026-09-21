import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.domains.auth.dependencies import require_permissions, require_roles
from app.domains.auth.models import User, UserRole
from app.domains.common.outbox import AuditLog, EventStatus, IntegrationEvent
from app.domains.common.outbox_service import OutboxService
from app.domains.integrations.schemas import IntegrationConfigRead, IntegrationOperationRead

router = APIRouter()

FAILURE_STATUSES = (
    EventStatus.PENDING_CONFIGURATION,
    EventStatus.FAILED_TERMINAL,
    EventStatus.FAILED,
    EventStatus.DEAD_LETTER,
)
OperationType = Literal["activate_pending", "park_unconfigured"]
OUTBOX_OPERATION_ACTIONS: dict[str, OperationType] = {
    "integration.outbox.activate_pending": "activate_pending",
    "integration.outbox.park_unconfigured": "park_unconfigured",
}


def _middleware_delivery_ready() -> bool:
    return all(
        (
            settings.middleware_enabled,
            settings.middleware_url,
            settings.middleware_ca_file,
            settings.middleware_client_cert_file,
            settings.middleware_client_key_file,
            settings.middleware_hmac_key_id,
            settings.middleware_hmac_secret_file,
            settings.middleware_service_identity,
            settings.middleware_audience,
            settings.middleware_tenant,
            settings.middleware_scope,
        )
    )


def _integration_config() -> IntegrationConfigRead:
    return IntegrationConfigRead(
        middleware_enabled=settings.middleware_enabled,
        middleware_url_configured=bool(settings.middleware_url),
        middleware_ca_configured=bool(settings.middleware_ca_file),
        middleware_client_certificate_configured=bool(
            settings.middleware_client_cert_file and settings.middleware_client_key_file
        ),
        middleware_hmac_configured=bool(
            settings.middleware_hmac_key_id and settings.middleware_hmac_secret_file
        ),
        middleware_identity_configured=bool(
            settings.middleware_service_identity
            and settings.middleware_audience
            and settings.middleware_tenant
            and settings.middleware_scope
        ),
        odoo_enabled=settings.odoo_enabled,
        odoo_url_configured=bool(settings.odoo_url),
        odoo_credentials_configured=bool(
            settings.odoo_database and settings.odoo_username and settings.odoo_api_key
        ),
    )


async def _status_counts(session: AsyncSession) -> dict[str, int]:
    rows = (
        await session.execute(
            select(IntegrationEvent.status, func.count(IntegrationEvent.id)).group_by(
                IntegrationEvent.status
            )
        )
    ).all()
    return {
        status.value if isinstance(status, EventStatus) else str(status): int(count)
        for status, count in rows
    }


def _operation_read(row: AuditLog) -> IntegrationOperationRead:
    metadata = row.metadata_json or {}
    operation_type = OUTBOX_OPERATION_ACTIONS[row.action]
    before_counts = metadata.get("before_counts")
    after_counts = metadata.get("after_counts")
    affected_count = metadata.get("affected_count")
    if not isinstance(before_counts, dict) or not isinstance(after_counts, dict):
        raise RuntimeError("integration operation audit record is malformed")
    return IntegrationOperationRead(
        id=row.resource_id,
        operation_type=operation_type,
        actor_id=row.actor_id,
        before_counts={str(key): int(value) for key, value in before_counts.items()},
        after_counts={str(key): int(value) for key, value in after_counts.items()},
        affected_count=int(affected_count or 0),
        created_at=row.created_at,
    )


async def _operate_outbox(
    session: AsyncSession,
    actor: User,
    operation_type: OperationType,
) -> IntegrationOperationRead:
    before_counts = await _status_counts(session)
    service = OutboxService(session)
    if operation_type == "activate_pending":
        if not _middleware_delivery_ready():
            raise HTTPException(
                409,
                "Middleware delivery is disabled or incompletely configured",
            )
        affected_count = await service.activate_pending_configuration(commit=False)
        action = "integration.outbox.activate_pending"
    else:
        affected_count = await service.park_unconfigured(commit=False)
        action = "integration.outbox.park_unconfigured"
    after_counts = await _status_counts(session)
    operation_id = uuid.uuid4()
    created_at = datetime.now(UTC)
    session.add(
        AuditLog(
            actor_id=actor.id,
            actor_type="user",
            action=action,
            resource_type="integration_outbox_operation",
            resource_id=operation_id,
            metadata_json={
                "operation_type": operation_type,
                "before_counts": before_counts,
                "after_counts": after_counts,
                "affected_count": affected_count,
            },
            created_at=created_at,
        )
    )
    await session.commit()
    return IntegrationOperationRead(
        id=operation_id,
        operation_type=operation_type,
        actor_id=actor.id,
        before_counts=before_counts,
        after_counts=after_counts,
        affected_count=affected_count,
        created_at=created_at,
    )


@router.get("/config", response_model=IntegrationConfigRead)
async def integration_config(
    _: User = Depends(require_permissions("admin.integrations.read")),
) -> IntegrationConfigRead:
    return _integration_config()


@router.get("/operations", response_model=list[IntegrationOperationRead])
async def integration_operations(
    limit: int = Query(200, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permissions("admin.integrations.read")),
) -> list[IntegrationOperationRead]:
    rows = list(
        (
            await session.scalars(
                select(AuditLog)
                .where(
                    AuditLog.resource_type == "integration_outbox_operation",
                    AuditLog.action.in_(tuple(OUTBOX_OPERATION_ACTIONS)),
                )
                .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
                .limit(limit)
            )
        ).all()
    )
    return [_operation_read(row) for row in rows]


@router.post("/outbox/activate-pending", response_model=IntegrationOperationRead)
async def activate_pending_outbox(
    session: AsyncSession = Depends(get_db),
    actor: User = Depends(require_permissions("admin.integrations.manage")),
) -> IntegrationOperationRead:
    return await _operate_outbox(session, actor, "activate_pending")


@router.post("/outbox/park-unconfigured", response_model=IntegrationOperationRead)
async def park_unconfigured_outbox(
    session: AsyncSession = Depends(get_db),
    actor: User = Depends(require_permissions("admin.integrations.manage")),
) -> IntegrationOperationRead:
    return await _operate_outbox(session, actor, "park_unconfigured")


@router.get("/health")
async def provider_health(_: User = Depends(require_roles(UserRole.finance, UserRole.admin))):
    return {
        "stripe": {"configured": bool(settings.stripe_secret_key)},
        "email": {"configured": bool(settings.smtp_host and settings.smtp_from_email)},
        "sms": {"configured": bool(settings.sms_provider and settings.sms_api_key)},
        "odoo": {
            "configured": bool(
                settings.odoo_url
                and settings.odoo_database
                and settings.odoo_username
                and settings.odoo_api_key
            )
        },
        "geocoder": {
            "configured": bool(settings.geocoding_api_key),
            "provider": settings.geocoding_provider,
        },
        "payout": {"configured": bool(settings.payout_provider)},
    }


@router.get("/failures")
async def failures(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(UserRole.finance, UserRole.admin)),
):
    return list(
        (
            await session.scalars(
                select(IntegrationEvent)
                .where(IntegrationEvent.status.in_(FAILURE_STATUSES))
                .order_by(IntegrationEvent.created_at.desc())
                .limit(200)
            )
        ).all()
    )


@router.post("/events/{event_id}/retry")
async def retry_event(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.finance, UserRole.admin)),
):
    try:
        return await OutboxService(session).retry(event_id, user.id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
