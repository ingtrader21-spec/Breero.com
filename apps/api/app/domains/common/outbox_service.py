import random
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Awaitable, Callable

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .outbox import AuditLog, EventStatus, IntegrationEvent

MAX_ATTEMPTS = 5
DEFAULT_LEASE_SECONDS = 300
INTEGRATION_DISABLED_ERROR_CODE = "INTEGRATION_DISABLED"


class OutboxService:
    def __init__(self, session: AsyncSession): self.session = session

    async def _sync_public_submission_status(
        self,
        events: list[IntegrationEvent],
        downstream_status: str,
    ) -> None:
        submission_ids = [
            event.aggregate_id
            for event in events
            if event.aggregate_type == "public_submission"
        ]
        if not submission_ids:
            return

        # Local import avoids coupling common outbox models to a domain model at import time.
        from app.domains.public_submissions.models import DownstreamStatus, PublicSubmission

        await self.session.execute(
            update(PublicSubmission)
            .where(PublicSubmission.id.in_(submission_ids))
            .values(downstream_status=DownstreamStatus(downstream_status))
        )

    async def activate_pending_configuration(
        self, event_prefix: str = "breero.", aggregate_type: str = "public_submission"
    ) -> int:
        events = list((await self.session.scalars(select(IntegrationEvent).where(
            IntegrationEvent.aggregate_type == aggregate_type,
            IntegrationEvent.status == EventStatus.PENDING_CONFIGURATION,
            IntegrationEvent.event_type.like(f"{event_prefix}%"),
        ).with_for_update(skip_locked=True))).all())
        now = datetime.now(UTC)
        for event in events:
            event.status = EventStatus.PENDING
            event.next_attempt_at = now
            if event.last_error_code == INTEGRATION_DISABLED_ERROR_CODE:
                event.last_error = None
                event.last_error_code = None
                event.last_error_at = None
        await self._sync_public_submission_status(events, "PENDING")
        await self.session.commit()
        return len(events)

    async def park_unconfigured(
        self, event_prefix: str = "breero.", aggregate_type: str = "public_submission"
    ) -> int:
        events = list(
            (
                await self.session.scalars(
                    select(IntegrationEvent)
                    .where(
                        IntegrationEvent.aggregate_type == aggregate_type,
                        IntegrationEvent.event_type.like(f"{event_prefix}%"),
                        IntegrationEvent.status.in_(
                            [
                                EventStatus.PENDING,
                                EventStatus.RETRYING,
                                EventStatus.FAILED_RETRYABLE,
                                EventStatus.PROCESSING,
                            ]
                        ),
                    )
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        now = datetime.now(UTC)
        for event in events:
            event.status = EventStatus.PENDING_CONFIGURATION
            event.claimed_at = None
            event.lease_expires_at = None
            event.claim_token = None
            event.last_error = "Integration disabled or unconfigured"
            event.last_error_code = INTEGRATION_DISABLED_ERROR_CODE
            event.last_error_at = now
        await self._sync_public_submission_status(events, "PENDING_CONFIGURATION")
        await self.session.commit()
        return len(events)

    async def claim(
        self,
        limit: int = 50,
        *,
        now: datetime | None = None,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
    ) -> list[IntegrationEvent]:
        now = now or datetime.now(UTC)
        events = list((await self.session.scalars(
            select(IntegrationEvent).where(
                or_(
                    and_(
                        IntegrationEvent.status.in_([
                            EventStatus.PENDING,
                            EventStatus.RETRYING,
                            EventStatus.FAILED_RETRYABLE,
                        ]),
                        IntegrationEvent.next_attempt_at <= now,
                    ),
                    and_(
                        IntegrationEvent.status == EventStatus.PROCESSING,
                        IntegrationEvent.lease_expires_at <= now,
                    ),
                )
            ).order_by(IntegrationEvent.created_at).with_for_update(skip_locked=True).limit(limit)
        )).all())
        for event in events:
            event.status = EventStatus.PROCESSING
            event.claimed_at = now
            event.lease_expires_at = now + timedelta(seconds=lease_seconds)
            event.claim_token = uuid.uuid4()
            event.attempt_count += 1
        # Commit makes the claim visible before slow network work; competing workers cannot claim it.
        await self.session.commit()
        return events

    async def process(self, deliver: Callable[[IntegrationEvent], Awaitable[object]], limit=50) -> int:
        events = await self.claim(limit)
        for event in events:
            try:
                result = await deliver(event)
                event.status = EventStatus.DELIVERED
                event.processed_at = datetime.now(UTC)
                event.last_error = None
                event.last_error_code = None
                if result is not None:
                    event.external_model = getattr(result, "model", None)
                    external_id = getattr(result, "external_id", None)
                    event.external_record_id = str(external_id) if external_id is not None else None
            except Exception as exc:
                # Persist a bounded, secret-safe diagnostic. Never persist URLs, credentials, or payloads.
                message = re.sub(r"(?i)(password|secret|token|api[_-]?key)\s*[:=]\s*\S+", r"\1=[REDACTED]", str(exc))
                event.last_error = message[:500]
                event.last_error_code = getattr(exc, "code", type(exc).__name__).upper()[:80]
                event.last_error_at = datetime.now(UTC)
                terminal = bool(getattr(exc, "terminal", False))
                if bool(getattr(exc, "pending_configuration", False)):
                    event.status = EventStatus.PENDING_CONFIGURATION
                    event.processed_at = None
                elif terminal or event.attempt_count >= MAX_ATTEMPTS:
                    event.status = EventStatus.FAILED_TERMINAL
                    event.processed_at = datetime.now(UTC)
                else:
                    event.status = EventStatus.RETRYING
                    event.next_attempt_at = datetime.now(UTC) + timedelta(
                        seconds=min(30 * 2 ** (event.attempt_count - 1), 3600) + random.randint(0, 15)
                    )
            event.lease_expires_at = None
            event.claim_token = None
            await self.session.commit()
        return len(events)

    async def retry(self, event_id: uuid.UUID, actor_id: uuid.UUID) -> IntegrationEvent:
        event = await self.session.scalar(
            select(IntegrationEvent).where(IntegrationEvent.id == event_id).with_for_update()
        )
        if not event:
            raise LookupError("Integration event not found")
        if event.status not in (
            EventStatus.DEAD_LETTER, EventStatus.FAILED, EventStatus.FAILED_TERMINAL,
            EventStatus.PENDING_CONFIGURATION,
        ):
            raise ValueError("Only failed or configuration-pending integration events can be retried")
        event.status = EventStatus.PENDING
        event.attempt_count = 0
        event.next_attempt_at = datetime.now(UTC)
        event.processed_at = None
        event.claimed_at = None
        event.lease_expires_at = None
        event.claim_token = None
        self.session.add(AuditLog(actor_id=actor_id, action="integration.retry",
            resource_type="integration_event", resource_id=event.id,
            metadata_json={"previous_error": event.last_error}, created_at=datetime.now(UTC)))
        await self.session.commit()
        return event
