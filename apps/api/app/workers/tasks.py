import asyncio
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.worker_session import WorkerSessionLocal
from app.domains.booking.models import EXPIRING_BOOKING_STATUSES, Booking, BookingStatus
from app.domains.common.outbox_service import OutboxService
from app.domains.finance.service import FinanceService
from app.domains.public_submissions.models import DownstreamStatus, PublicSubmission
from app.integrations.email import EmailAdapter
from app.integrations.middleware import MiddlewareAdapter
from app.workers.celery_app import celery_app


async def expire_booking_holds(session: AsyncSession, *, now: datetime) -> int:
    """Expire only currently expirable booking states at or before ``now``.

    Capacity queries independently ignore expired holds by ``expires_at`` so delayed
    worker execution cannot consume capacity. This cleanup is intentionally idempotent:
    once a booking becomes ``EXPIRED`` it is no longer selected on later runs.
    """
    rows = list(
        (
            await session.scalars(
                select(Booking)
                .where(
                    Booking.status.in_(EXPIRING_BOOKING_STATUSES),
                    Booking.expires_at <= now,
                )
                .with_for_update(skip_locked=True)
            )
        ).all()
    )
    for booking in rows:
        booking.status = BookingStatus.EXPIRED
    await session.commit()
    return len(rows)


@celery_app.task(name="app.workers.tasks.expire_bookings")
def expire_bookings() -> int:
    async def run() -> int:
        async with WorkerSessionLocal() as session:
            return await expire_booking_holds(session, now=datetime.now(UTC))

    return asyncio.run(run())


class UnhandledOutboxEvent(RuntimeError):
    code = "UNHANDLED_EVENT_TYPE"
    terminal = True


async def deliver_outbox_event(event, session, adapter, email):
    notification_events = {
        "email_verification_requested",
        "password_reset_requested",
        "password_changed",
        "payment_captured",
        "refund_created",
    }
    if event.event_type in notification_events:
        await email.send(event.event_type, event.payload)
        return None
    if event.event_type.startswith("breero."):
        result = await adapter.deliver(event)
        if event.aggregate_type == "public_submission":
            submission = await session.get(PublicSubmission, event.aggregate_id)
            if submission:
                submission.downstream_status = DownstreamStatus.DELIVERED
        return result
    # A no-op is not delivery. Retain the event for reviewed handler installation
    # and authorized replay; keep payload and event type out of diagnostics.
    raise UnhandledOutboxEvent("No approved handler is registered for this event")


@celery_app.task(
    name="app.workers.tasks.publish_outbox",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=5,
)
def publish_outbox() -> int:
    async def run() -> int:
        async with WorkerSessionLocal() as session:
            adapter = MiddlewareAdapter()
            email = EmailAdapter()
            async def deliver(event):
                return await deliver_outbox_event(event, session, adapter, email)

            outbox = OutboxService(session)
            if settings.middleware_enabled:
                await outbox.activate_pending_configuration()
            else:
                await outbox.park_unconfigured()
            return await outbox.process(deliver)

    return asyncio.run(run())


@celery_app.task(name="app.workers.tasks.release_earnings")
def release_earnings() -> int:
    async def run() -> int:
        async with WorkerSessionLocal() as session:
            return await FinanceService(session).release_eligible()

    return asyncio.run(run())


@celery_app.task(name="app.workers.tasks.generate_weekly_payout_candidates")
def generate_weekly_payout_candidates() -> str:
    async def run() -> str:
        async with WorkerSessionLocal() as session:
            try:
                batch = await FinanceService(session).create_batch("USD")
                return str(batch.id)
            except Exception as exc:
                # A no-candidate week is expected; unexpected task failures remain visible in Celery.
                if getattr(exc, "status_code", None) == 409:
                    return "no_candidates"
                raise

    return asyncio.run(run())
