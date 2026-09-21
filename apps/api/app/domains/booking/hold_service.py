import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.domains.booking.capacity_models import BookingCapacityHold, CapacityHoldStatus
from app.domains.booking.matching import ProviderMatcher
from app.domains.booking.models import Address
from app.domains.booking.repository import BookingRepository
from app.domains.booking.timezones import enforce_breero_hours, local_interval
from app.domains.catalog.models import Service
from app.domains.common.outbox import AuditLog

HOLD_DURATION = timedelta(minutes=30)
MAX_ACTIVE_HOLDS_PER_OWNER = 3


def owner_fingerprint(value: str) -> str:
    normalized = value.strip()
    if len(normalized) < 16:
        raise DomainError("AUTH_REQUIRED", "A booking session is required", 401)
    return hashlib.sha256(normalized.encode()).hexdigest()


class CapacityHoldService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = BookingRepository(session)
        self.matcher = ProviderMatcher(session)

    async def create(
        self,
        service_id: uuid.UUID,
        address_id: uuid.UUID,
        start_local: datetime,
        timezone_id: str,
        booking_session: str,
        idempotency_key: str,
        *,
        emergency: bool = False,
    ) -> BookingCapacityHold:
        fingerprint = owner_fingerprint(booking_session)
        await self.repository.lock_idempotency_key(f"capacity-hold:{idempotency_key}")
        existing = await self.session.scalar(
            select(BookingCapacityHold).where(BookingCapacityHold.idempotency_key == idempotency_key)
        )
        if existing:
            if existing.owner_fingerprint_hash != fingerprint:
                raise DomainError("HOLD_CONFLICT", "Idempotency key belongs to another booking session", 409)
            return existing
        service = await self.session.get(Service, service_id)
        address = await self.session.get(Address, address_id)
        if not service or not service.is_active or not service.is_bookable:
            raise DomainError("SERVICE_NOT_BOOKABLE", "The selected service is not bookable", 422)
        if service.quote_required:
            raise DomainError("QUOTE_REQUIRED", "The selected service requires a quote", 422)
        if not address or not (address.service_zone_id or address.service_area_id):
            raise DomainError("OUTSIDE_SERVICE_AREA", "The address is outside an active service area", 422)
        if timezone_id != address.timezone_name:
            raise DomainError("TIMEZONE_UNRESOLVED", "Slot timezone must match the service address", 422)
        duration = service.duration_minutes or 60
        end_local = start_local + timedelta(
            minutes=duration + service.before_buffer_minutes + service.after_buffer_minutes
        )
        enforce_breero_hours(
            start_local,
            end_local,
            service_emergency_eligible=service.emergency_eligible,
            provider_sunday_emergency_enabled=True,
        )
        interval = local_interval(start_local, end_local, timezone_id)
        candidates = await self.matcher.candidates(
            service, address, interval.start_utc, interval.end_utc, emergency=emergency
        )
        if not candidates:
            raise DomainError("NO_CAPACITY", "No appointments are available for the selected time", 409)
        chosen = candidates[0]
        await self.repository.lock_provider_slot(chosen.professional_id, interval.start_utc)
        refreshed = await self.matcher.candidates(
            service,
            address,
            interval.start_utc,
            interval.end_utc,
            emergency=emergency,
            professional_id=chosen.professional_id,
        )
        if not refreshed:
            raise DomainError("HOLD_CONFLICT", "The selected slot is no longer available", 409)
        now = datetime.now(UTC)
        active_count = int(
            await self.session.scalar(
                select(func.count(BookingCapacityHold.id)).where(
                    BookingCapacityHold.owner_fingerprint_hash == fingerprint,
                    BookingCapacityHold.status == CapacityHoldStatus.HELD,
                    BookingCapacityHold.expires_at > now,
                )
            )
            or 0
        )
        if active_count >= MAX_ACTIVE_HOLDS_PER_OWNER:
            raise DomainError("RATE_LIMITED", "Too many active capacity holds", 429)
        hold = BookingCapacityHold(
            service_id=service.id,
            address_id=address.id,
            provider_candidate_id=chosen.provider_id,
            professional_candidate_id=chosen.professional_id,
            slot_start_utc=interval.start_utc,
            slot_end_utc=interval.end_utc,
            timezone_id=timezone_id,
            capacity_minutes=chosen.capacity_minutes,
            status=CapacityHoldStatus.HELD,
            expires_at=now + HOLD_DURATION,
            owner_fingerprint_hash=fingerprint,
            idempotency_key=idempotency_key,
        )
        self.session.add(hold)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            raise DomainError("HOLD_CONFLICT", "The selected slot is no longer available", 409) from exc
        self._audit(hold, "capacity_hold.created")
        await self.session.commit()
        await self.session.refresh(hold)
        return hold

    async def get(self, hold_id: uuid.UUID, booking_session: str) -> BookingCapacityHold:
        hold = await self.session.get(BookingCapacityHold, hold_id)
        if not hold or hold.owner_fingerprint_hash != owner_fingerprint(booking_session):
            raise DomainError("HOLD_NOT_FOUND", "Capacity hold not found", 404)
        if hold.status == CapacityHoldStatus.HELD and hold.expires_at <= datetime.now(UTC):
            hold.status = CapacityHoldStatus.EXPIRED
            await self.session.commit()
        return hold

    async def release(self, hold_id: uuid.UUID, booking_session: str) -> None:
        fingerprint = owner_fingerprint(booking_session)
        hold = await self.session.scalar(
            select(BookingCapacityHold)
            .where(BookingCapacityHold.id == hold_id)
            .with_for_update()
        )
        if not hold or hold.owner_fingerprint_hash != fingerprint:
            raise DomainError("HOLD_NOT_FOUND", "Capacity hold not found", 404)
        if hold.status == CapacityHoldStatus.HELD:
            hold.status = CapacityHoldStatus.RELEASED
            hold.released_at = datetime.now(UTC)
            self._audit(hold, "capacity_hold.released")
            await self.session.commit()

    async def expire_stale(self) -> int:
        now = datetime.now(UTC)
        result = await self.session.execute(
            update(BookingCapacityHold)
            .where(
                BookingCapacityHold.status == CapacityHoldStatus.HELD,
                BookingCapacityHold.expires_at <= now,
            )
            .values(status=CapacityHoldStatus.EXPIRED)
        )
        await self.session.commit()
        return int(cast(CursorResult[object], result).rowcount or 0)

    def _audit(self, hold: BookingCapacityHold, action: str) -> None:
        self.session.add(
            AuditLog(
                actor_id=None,
                actor_type="booking_session",
                action=action,
                resource_type="capacity_hold",
                resource_id=hold.id,
                metadata_json={
                    "expires_at": hold.expires_at.isoformat(),
                    "timezone_id": hold.timezone_id,
                },
                created_at=datetime.now(UTC),
            )
        )
