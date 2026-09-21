import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.domains.booking.models import (
    Address,
    Booking,
    BookingStatus,
    ProviderServiceCoverage,
    ProviderWorkingHours,
)
from app.domains.booking.repository import BookingRepository
from app.domains.common.outbox import AuditLog, EventStatus, IntegrationEvent
from app.domains.dispatch.models import Assignment, AssignmentStatus
from app.domains.jobs.models import Job, JobStatus
from app.domains.workforce.models import (
    ProviderCredential,
    ProviderCredentialType,
    Vendor,
    VendorStatus,
    Worker,
    WorkerStatus,
)


class OperatorSchedulingService:
    """All final scheduling decisions pass through an authorized operator transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = BookingRepository(session)

    async def _locked_booking(self, booking_id: uuid.UUID) -> Booking:
        booking = await self.session.scalar(
            select(Booking).where(Booking.id == booking_id).with_for_update()
        )
        if not booking:
            raise DomainError("BOOKING_NOT_FOUND", "Booking not found", 404)
        return booking

    async def _qualified_worker(self, booking: Booking, worker_id: uuid.UUID) -> tuple[Worker, Vendor]:
        now = datetime.now(UTC)
        if booking.expires_at <= now and booking.status != BookingStatus.CONFIRMED:
            booking.status = BookingStatus.EXPIRED
            raise DomainError("HOLD_EXPIRED", "The tentative hold has expired", 409)
        address = await self.session.get(Address, booking.address_id)
        if not address or not address.state_code or not address.timezone_name:
            raise DomainError("ADDRESS_NOT_VALIDATED", "A validated address and timezone are required", 422)
        try:
            local_zone = ZoneInfo(address.timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise DomainError("ADDRESS_TIMEZONE_INVALID", "Service address timezone is invalid", 422) from exc
        local_start = booking.window_start.astimezone(local_zone)
        local_end = booking.window_end.astimezone(local_zone)
        worker = await self.session.get(Worker, worker_id)
        vendor = await self.session.get(Vendor, worker.vendor_id) if worker else None
        if not worker or not vendor or worker.status != WorkerStatus.ACTIVE or not worker.available:
            raise DomainError("PROVIDER_UNAVAILABLE", "The selected provider is unavailable", 409)
        if vendor.status != VendorStatus.ACTIVE:
            raise DomainError("PROVIDER_NOT_APPROVED", "The selected provider is not approved", 409)
        coverage = await self.session.scalar(
            select(ProviderServiceCoverage.id).where(
                ProviderServiceCoverage.worker_id == worker.id,
                ProviderServiceCoverage.service_id == booking.service_id,
                ProviderServiceCoverage.postal_code == address.postal_code[:5],
                ProviderServiceCoverage.active.is_(True),
            )
        )
        hours = await self.session.scalar(
            select(ProviderWorkingHours).where(
                ProviderWorkingHours.worker_id == worker.id,
                ProviderWorkingHours.weekday == local_start.weekday(),
            )
        )
        if not coverage or not hours or local_start.time() < hours.start_time or local_end.time() > hours.end_time:
            raise DomainError("PROVIDER_OUT_OF_COVERAGE", "Provider coverage or working hours do not support this request", 409)
        valid_types = set(
            (await self.session.scalars(
                select(ProviderCredential.credential_type).where(
                    ProviderCredential.vendor_id == vendor.id,
                    ProviderCredential.jurisdiction.in_([address.state_code, "US"]),
                    ProviderCredential.verified.is_(True),
                    ProviderCredential.verified_at.is_not(None),
                    ProviderCredential.expires_on >= local_start.date(),
                )
            )).all()
        )
        required = {ProviderCredentialType.LICENSE, ProviderCredentialType.INSURANCE}
        if not required.issubset(valid_types):
            raise DomainError("PROVIDER_CREDENTIALS_INVALID", "Current verified license and insurance are required", 409)
        await self.repository.lock_provider_slot(worker.id, booking.window_start)
        overlaps = await self.session.scalar(
            select(func.count(Job.id)).where(
                Job.worker_id == worker.id,
                Job.id != select(Job.id).where(Job.booking_id == booking.id).scalar_subquery(),
                Job.scheduled_start < booking.window_end,
                Job.scheduled_end > booking.window_start,
                Job.status.not_in([JobStatus.CANCELLED, JobStatus.COMPLETED]),
            )
        )
        if int(overlaps or 0) >= hours.capacity:
            raise DomainError("PROVIDER_CAPACITY_UNAVAILABLE", "Provider capacity is no longer available", 409)
        return worker, vendor

    async def confirm(self, booking_id: uuid.UUID, worker_id: uuid.UUID, actor_id: uuid.UUID, reason: str) -> Job:
        booking = await self._locked_booking(booking_id)
        if booking.status not in {
            BookingStatus.REQUESTED,
            BookingStatus.PENDING_MANUAL_DISPATCH,
            BookingStatus.TENTATIVE_HOLD,
            BookingStatus.PROVIDER_ASSIGNED,
        }:
            raise DomainError("BOOKING_NOT_CONFIRMABLE", "Booking is not awaiting operator confirmation", 409)
        worker, vendor = await self._qualified_worker(booking, worker_id)
        existing = await self.session.scalar(select(Job).where(Job.booking_id == booking.id))
        if existing:
            if existing.worker_id != worker.id:
                raise DomainError("BOOKING_ASSIGNMENT_MISMATCH", "Assigned professional does not match", 409)
            job = existing
        else:
            job = Job(
                booking_id=booking.id, customer_id=booking.customer_id, service_id=booking.service_id,
                address_id=booking.address_id, status=JobStatus.ASSIGNED,
                scheduled_start=booking.window_start, scheduled_end=booking.window_end,
                vendor_id=vendor.id, worker_id=worker.id,
            )
            self.session.add(job)
            await self.session.flush()
            self.session.add(Assignment(
                job_id=job.id, vendor_id=vendor.id, worker_id=worker.id,
                status=AssignmentStatus.ACTIVE, assigned_by=actor_id,
            ))
        booking.provider_worker_id = worker.id
        booking.status = BookingStatus.CONFIRMED
        self._record(booking, actor_id, "booking.operator_confirm", reason, worker.id)
        self.session.add(IntegrationEvent(
            aggregate_type="booking", aggregate_id=booking.id,
            event_type="booking.confirmed", aggregate_version=1, schema_version=1,
            idempotency_key=f"booking.confirmed:{booking.id}",
            payload={"booking_id": str(booking.id), "job_id": str(job.id), "payment_required": False},
            status=EventStatus.PENDING, next_attempt_at=datetime.now(UTC),
        ))
        await self.session.commit()
        await self.session.refresh(job)
        return job

    def _record(self, booking: Booking, actor_id: uuid.UUID, action: str, reason: str, worker_id: uuid.UUID | None = None) -> None:
        self.session.add(AuditLog(
            actor_id=actor_id, actor_type="user", action=action,
            resource_type="booking", resource_id=booking.id,
            metadata_json={"reason": reason, "worker_id": str(worker_id) if worker_id else None},
            created_at=datetime.now(UTC),
        ))
