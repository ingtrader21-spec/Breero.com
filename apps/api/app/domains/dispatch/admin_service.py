import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.errors import DomainError
from app.domains.booking.capacity_models import AssignmentMethod, ProviderAssignmentHistory
from app.domains.booking.matching import ProviderCandidate, ProviderMatcher
from app.domains.booking.models import Address, Booking, BookingStatus
from app.domains.booking.repository import BookingRepository
from app.domains.catalog.models import Service
from app.domains.common.outbox import AuditLog
from app.domains.dispatch.models import Assignment, AssignmentStatus
from app.domains.jobs.models import Job, JobStatus
from app.domains.workforce.models import Worker


class AdminDispatchService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def candidates(self, booking_id: uuid.UUID) -> list[ProviderCandidate]:
        booking = await self.session.get(Booking, booking_id)
        if not booking:
            raise DomainError("BOOKING_NOT_FOUND", "Booking not found", 404)
        address = await self.session.get(Address, booking.address_id)
        service = await self.session.get(Service, booking.service_id)
        if not address or not service:
            raise DomainError("INVALID_BOOKING", "Booking service or address is missing", 422)
        return await ProviderMatcher(self.session).candidates(
            service, address, booking.window_start, booking.window_end
        )

    async def assign(
        self,
        booking_id: uuid.UUID,
        professional_id: uuid.UUID,
        actor_id: uuid.UUID,
        reason: str,
        *,
        reassign: bool = False,
        assignment_method: AssignmentMethod = AssignmentMethod.MANUAL,
    ) -> Booking:
        if assignment_method == AssignmentMethod.MANUAL and settings.provider_assignment_mode != "MANUAL":
            raise DomainError("FORBIDDEN", "Protected release permits manual dispatch only", 403)
        if assignment_method == AssignmentMethod.AUTOMATIC and not (
            settings.provider_assignment_mode == "AUTOMATIC"
            and settings.auto_assign_provider
            and settings.live_provider_dispatch
        ):
            raise DomainError("FORBIDDEN", "Automatic provider dispatch is disabled", 403)
        booking = await self.session.scalar(
            select(Booking).where(Booking.id == booking_id).with_for_update()
        )
        if not booking:
            raise DomainError("BOOKING_NOT_FOUND", "Booking not found", 404)
        allowed = {
            BookingStatus.REQUESTED,
            BookingStatus.PENDING_REVIEW,
            BookingStatus.PENDING_MANUAL_DISPATCH,
            BookingStatus.AWAITING_ASSIGNMENT,
            BookingStatus.REASSIGNMENT_REQUIRED,
            BookingStatus.PROVIDER_ASSIGNED,
        }
        if booking.status not in allowed:
            raise DomainError("INVALID_STATE_TRANSITION", "Booking is not assignable", 409)
        candidates = await self.candidates(booking.id)
        candidate = next(
            (item for item in candidates if item.professional_id == professional_id), None
        )
        if not candidate:
            raise DomainError("NO_CAPACITY", "Professional is not an eligible candidate", 409)
        await BookingRepository(self.session).lock_provider_slot(
            professional_id, booking.window_start
        )
        candidates = await self.candidates(booking.id)
        candidate = next(
            (item for item in candidates if item.professional_id == professional_id), None
        )
        if not candidate:
            raise DomainError("NO_CAPACITY", "Professional capacity changed", 409)
        worker = await self.session.get(Worker, professional_id)
        if not worker:
            raise DomainError("NO_PROVIDER_COVERAGE", "Professional is unavailable", 409)
        job = await self.session.scalar(select(Job).where(Job.booking_id == booking.id))
        previous_worker_id = booking.provider_worker_id
        previous_provider_id = None
        if job:
            previous_provider_id = job.vendor_id
            active = await self.session.scalar(
                select(Assignment).where(
                    Assignment.job_id == job.id,
                    Assignment.status == AssignmentStatus.ACTIVE,
                )
            )
            if active:
                active.status = AssignmentStatus.RELEASED
                active.released_at = datetime.now(UTC)
                await self.session.flush()
            job.vendor_id = worker.vendor_id
            job.worker_id = worker.id
            job.status = JobStatus.ASSIGNED
        else:
            job = Job(
                booking_id=booking.id,
                customer_id=booking.customer_id,
                service_id=booking.service_id,
                address_id=booking.address_id,
                status=JobStatus.ASSIGNED,
                scheduled_start=booking.window_start,
                scheduled_end=booking.window_end,
                vendor_id=worker.vendor_id,
                worker_id=worker.id,
            )
            self.session.add(job)
            await self.session.flush()
        self.session.add(
            Assignment(
                job_id=job.id,
                vendor_id=worker.vendor_id,
                worker_id=worker.id,
                status=AssignmentStatus.ACTIVE,
                assigned_by=actor_id,
            )
        )
        booking.provider_worker_id = worker.id
        booking.recommended_provider_id = candidate.provider_id
        booking.recommended_professional_id = candidate.professional_id
        booking.assignment_score = candidate.score
        booking.assignment_reason = reason
        booking.status = BookingStatus.PROVIDER_ASSIGNED
        self.session.add(
            ProviderAssignmentHistory(
                booking_id=booking.id,
                previous_provider_id=previous_provider_id,
                new_provider_id=worker.vendor_id,
                previous_professional_id=previous_worker_id,
                new_professional_id=worker.id,
                reason=reason,
                assignment_method=assignment_method,
                score_at_assignment=candidate.score,
                performed_by=actor_id,
            )
        )
        self._audit(
            actor_id,
            booking.id,
            "booking.reassigned" if reassign else "booking.assigned",
            reason,
            worker.id,
            assignment_method,
        )
        await self.session.commit()
        await self.session.refresh(booking)
        return booking

    async def automatic_assign(self, booking_id: uuid.UUID, actor_id: uuid.UUID) -> Booking:
        candidates = await self.candidates(booking_id)
        if not candidates:
            raise DomainError("NO_CAPACITY", "No eligible provider candidates are available", 409)
        return await self.assign(
            booking_id,
            candidates[0].professional_id,
            actor_id,
            "automatic_match",
            assignment_method=AssignmentMethod.AUTOMATIC,
        )

    async def unassign(self, booking_id: uuid.UUID, actor_id: uuid.UUID, reason: str) -> Booking:
        booking = await self.session.scalar(
            select(Booking).where(Booking.id == booking_id).with_for_update()
        )
        if not booking or booking.status != BookingStatus.PROVIDER_ASSIGNED:
            raise DomainError("INVALID_STATE_TRANSITION", "Booking is not currently assigned", 409)
        job = await self.session.scalar(select(Job).where(Job.booking_id == booking.id))
        previous_provider_id = job.vendor_id if job else None
        if job:
            active = await self.session.scalar(
                select(Assignment).where(
                    Assignment.job_id == job.id,
                    Assignment.status == AssignmentStatus.ACTIVE,
                )
            )
            if active:
                active.status = AssignmentStatus.RELEASED
                active.released_at = datetime.now(UTC)
            job.vendor_id = None
            job.worker_id = None
            job.status = JobStatus.MATCHING
        previous_worker = booking.provider_worker_id
        booking.provider_worker_id = None
        booking.status = BookingStatus.REASSIGNMENT_REQUIRED
        self.session.add(
            ProviderAssignmentHistory(
                booking_id=booking.id,
                previous_provider_id=previous_provider_id,
                new_provider_id=None,
                previous_professional_id=previous_worker,
                new_professional_id=None,
                reason=reason,
                assignment_method=AssignmentMethod.MANUAL,
                score_at_assignment=None,
                performed_by=actor_id,
            )
        )
        self._audit(actor_id, booking.id, "booking.unassigned", reason, None)
        await self.session.commit()
        return booking

    def _audit(
        self,
        actor_id: uuid.UUID,
        booking_id: uuid.UUID,
        action: str,
        reason: str,
        worker_id: uuid.UUID | None,
        assignment_method: AssignmentMethod = AssignmentMethod.MANUAL,
    ) -> None:
        self.session.add(
            AuditLog(
                actor_id=actor_id,
                actor_type="user",
                action=action,
                resource_type="booking",
                resource_id=booking_id,
                metadata_json={
                    "reason": reason,
                    "worker_id": str(worker_id) if worker_id else None,
                    "assignment_method": assignment_method.value,
                    "live_dispatch": False,
                },
                created_at=datetime.now(UTC),
            )
        )
