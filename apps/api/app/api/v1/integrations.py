import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.domains.auth.dependencies import require_any_permission
from app.domains.auth.models import User
from app.domains.common.outbox import EventStatus, IntegrationEvent
from app.domains.common.outbox_service import OutboxService

router = APIRouter()

FAILURE_STATUSES = (
    EventStatus.PENDING_CONFIGURATION,
    EventStatus.FAILED_TERMINAL,
    EventStatus.FAILED,
    EventStatus.DEAD_LETTER,
)


@router.get("/health")
async def provider_health(
    _: User = Depends(
        require_any_permission(
            "admin.integrations.read",
            "finance.reconciliation.read",
        )
    ),
):
    return {
        "stripe": {"configured": bool(settings.stripe_secret_key)},
        "email": {
            "configured": bool(settings.email_enabled),
            "mode": settings.transactional_email_mode,
            "tenant_credentials": True,
        },
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
    _: User = Depends(
        require_any_permission(
            "admin.integrations.read",
            "finance.reconciliation.read",
        )
    ),
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
    user: User = Depends(require_any_permission("integration.retry")),
):
    try:
        return await OutboxService(session).retry(event_id, user.id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
