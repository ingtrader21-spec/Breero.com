import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.booking.models import Booking, BookingStatus
from app.domains.booking.scheduling import OperatorSchedulingService
from app.domains.common.outbox import AuditLog
from app.domains.jobs.models import Job, JobEvent, JobStatus
from app.domains.jobs.repository import JobRepository
from app.domains.jobs.service import JobService
from app.domains.workforce.models import Worker

from .models import Assignment, AssignmentStatus, DispatchOffer, OfferStatus
from .repository import DispatchRepository

ASSIGNABLE_JOB_STATUSES = frozenset({JobStatus.CREATED, JobStatus.MATCHING, JobStatus.OFFERED})
REASSIGNABLE_JOB_STATUSES = frozenset({JobStatus.ASSIGNED})


def reserved_slot_conflict(booking: Booking | None, worker_id: uuid.UUID) -> bool:
    """A booking-backed job may only be held by the worker reserving its provider slot."""
    return booking is not None and booking.provider_worker_id != worker_id


class DispatchService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = DispatchRepository(session)
        self.jobs = JobRepository(session)
        self.job_service = JobService(session)

    async def match(
        self, job_id: uuid.UUID, actor_id: uuid.UUID | None = None
    ) -> list[DispatchOffer]:
        job = await self.jobs.get(job_id, lock=True)
        if not job:
            raise HTTPException(404, "Job not found")
        if job.status not in ASSIGNABLE_JOB_STATUSES:
            raise HTTPException(409, "Job cannot be matched in its current state")
        existing = await self.repo.offers_for_job(job_id)
        round_number = max((offer.round for offer in existing), default=0) + 1
        booking = await self.session.get(Booking, job.booking_id)
        candidates = await self.repo.candidate_workers(
            [], limit=10, worker_id=booking.provider_worker_id if booking else None
        )
        if not candidates:
            if job.status != JobStatus.MATCHING:
                self.job_service.apply_transition(
                    job, JobStatus.MATCHING, actor_id, "system", "no_candidates"
                )
            await self.session.commit()
            return []
        now = datetime.now(UTC)
        offers: list[DispatchOffer] = []
        offered_vendors: set[uuid.UUID] = set()
        for vendor, worker in candidates:
            # Offers are unique per (job, vendor, round); one worker proposal per vendor.
            if vendor.id in offered_vendors:
                continue
            offered_vendors.add(vendor.id)
            rank = len(offers)
            offer = DispatchOffer(
                job_id=job.id,
                vendor_id=vendor.id,
                worker_id=worker.id,
                status=OfferStatus.PENDING,
                round=round_number,
                score=1000 - rank,
                score_detail={"availability": 100, "capability": 100},
                expires_at=now + timedelta(minutes=15),
            )
            self.session.add(offer)
            offers.append(offer)
        if job.status == JobStatus.CREATED:
            self.job_service.apply_transition(
                job, JobStatus.MATCHING, actor_id, "system", "matching_started"
            )
        self.job_service.apply_transition(
            job,
            JobStatus.OFFERED,
            actor_id,
            "system",
            "offers_created",
            {"count": len(offers), "round": round_number},
        )
        await self.session.commit()
        return offers

    async def decide_offer(
        self,
        offer_id: uuid.UUID,
        vendor_id: uuid.UUID,
        accept: bool,
        worker_id: uuid.UUID | None,
        actor_id: uuid.UUID,
    ) -> DispatchOffer:
        offer = await self.repo.get_offer(offer_id, lock=True)
        if not offer:
            raise HTTPException(404, "Offer not found")
        if offer.vendor_id != vendor_id:
            raise HTTPException(403, "Offer belongs to another vendor")
        if offer.status != OfferStatus.PENDING:
            raise HTTPException(409, "Offer is no longer pending")
        if offer.expires_at <= datetime.now(UTC):
            offer.status = OfferStatus.EXPIRED
            await self.session.commit()
            raise HTTPException(409, "Offer has expired")
        offer.responded_at = datetime.now(UTC)
        if not accept:
            offer.status = OfferStatus.DECLINED
            await self.session.commit()
            return offer
        selected_worker = worker_id or offer.worker_id
        worker = await self.session.scalar(
            select(Worker).where(
                Worker.id == selected_worker,
                Worker.vendor_id == vendor_id,
                Worker.available.is_(True),
            )
        )
        if not worker:
            raise HTTPException(409, "Selected worker is unavailable")
        job = await self.jobs.get(offer.job_id, lock=True)
        if not job or job.status not in {JobStatus.OFFERED, JobStatus.MATCHING}:
            raise HTTPException(409, "Job is no longer assignable")
        booking = await self.session.get(Booking, job.booking_id)
        if reserved_slot_conflict(booking, worker.id):
            raise HTTPException(409, "Worker does not hold the reserved provider slot")
        offer.status = OfferStatus.ACCEPTED
        assignment = Assignment(
                job_id=job.id,
                offer_id=offer.id,
                vendor_id=vendor_id,
                worker_id=worker.id,
                status=AssignmentStatus.ACTIVE,
                assigned_by=actor_id,
            )
        self.session.add(assignment)
        self.session.add(
            AuditLog(
                actor_id=actor_id,
                action="assignment.create",
                resource_type="job",
                resource_id=job.id,
                metadata_json={"vendor_id": str(vendor_id), "worker_id": str(worker.id)},
                created_at=datetime.now(UTC),
            )
        )
        job.vendor_id, job.worker_id = vendor_id, worker.id
        if booking and booking.provider_worker_id == worker.id and booking.status == BookingStatus.PENDING_PROVIDER_CONFIRMATION:
            booking.status = BookingStatus.CONFIRMED
        self.job_service.apply_transition(
            job, JobStatus.ASSIGNED, actor_id, "vendor", "offer_accepted"
        )
        # ``available`` is an operator-controlled participation switch. Overlap is enforced by
        # the provider-slot reservation, so assigning one future visit must not hide all others.
        await self.session.execute(
            update(DispatchOffer)
            .where(
                DispatchOffer.job_id == job.id,
                DispatchOffer.id != offer.id,
                DispatchOffer.status == OfferStatus.PENDING,
            )
            .values(status=OfferStatus.WITHDRAWN)
        )
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(409, "Job was assigned concurrently") from exc
        return offer

    async def manual_assign(self, job_id, vendor_id, worker_id, actor_id, reason) -> Assignment:
        job = await self.jobs.get(job_id, lock=True)
        worker = await self.session.scalar(
            select(Worker).where(
                Worker.id == worker_id, Worker.vendor_id == vendor_id, Worker.available.is_(True)
            )
        )
        if not job:
            raise HTTPException(404, "Job not found")
        if not worker:
            raise HTTPException(409, "Worker is unavailable or belongs to another vendor")
        if job.status not in ASSIGNABLE_JOB_STATUSES:
            raise HTTPException(409, "Job is not assignable")
        booking = await self.session.get(Booking, job.booking_id)
        if reserved_slot_conflict(booking, worker_id):
            raise HTTPException(409, "Worker does not hold the reserved provider slot")
        assignment = Assignment(
            job_id=job.id,
            vendor_id=vendor_id,
            worker_id=worker_id,
            status=AssignmentStatus.ACTIVE,
            assigned_by=actor_id,
        )
        self.session.add(assignment)
        self.session.add(
            AuditLog(
                actor_id=actor_id,
                action="assignment.create",
                resource_type="job",
                resource_id=job.id,
                metadata_json={
                    "vendor_id": str(vendor_id),
                    "worker_id": str(worker_id),
                    "reason": reason,
                },
                created_at=datetime.now(UTC),
            )
        )
        self.job_service.apply_transition(
            job, JobStatus.ASSIGNED, actor_id, "operations", reason
        )
        job.vendor_id, job.worker_id = vendor_id, worker_id
        if booking and booking.status == BookingStatus.PENDING_PROVIDER_CONFIRMATION:
            booking.status = BookingStatus.CONFIRMED
        # Same as offer acceptance: a manually assigned job must not keep live offers.
        await self.session.execute(
            update(DispatchOffer)
            .where(
                DispatchOffer.job_id == job.id,
                DispatchOffer.status == OfferStatus.PENDING,
            )
            .values(status=OfferStatus.WITHDRAWN)
        )
        await self.session.commit()
        await self.session.refresh(assignment)
        return assignment

    async def reassign(
        self,
        job_id: uuid.UUID,
        vendor_id: uuid.UUID,
        worker_id: uuid.UUID,
        actor_id: uuid.UUID,
        reason: str,
        expected_version: int | None = None,
    ) -> tuple[Assignment, Assignment, Job]:
        """Move an assigned, not-yet-travelling job to another qualified worker.

        Booking-backed jobs re-run the operator scheduling qualification (coverage,
        working hours, credentials, capacity) and move the reserved provider slot
        in the same transaction, so the booking/assignment invariant never splits.
        """
        job = await self.jobs.get(job_id, lock=True)
        if not job:
            raise HTTPException(404, "Job not found")
        if expected_version is not None and job.version != expected_version:
            raise HTTPException(409, "Job has changed since it was reviewed; reload and retry")
        if job.status not in REASSIGNABLE_JOB_STATUSES:
            raise HTTPException(409, "Only assigned jobs that have not started travel can be reassigned")
        current = await self.repo.active_assignment(job.id, lock=True)
        if not current:
            raise HTTPException(409, "Job has no active assignment to replace")
        if current.worker_id == worker_id:
            raise HTTPException(409, "Job is already assigned to this worker")

        booking = await self.session.get(Booking, job.booking_id)
        if booking is not None:
            worker, vendor = await OperatorSchedulingService(self.session)._qualified_worker(
                booking, worker_id
            )
            if vendor.id != vendor_id:
                raise HTTPException(409, "Worker is unavailable or belongs to another vendor")
            booking.provider_worker_id = worker.id
        elif not await self.repo.dispatchable_worker(worker_id, vendor_id):
            raise HTTPException(409, "Worker is unavailable or belongs to another vendor")

        now = datetime.now(UTC)
        previous_vendor_id, previous_worker_id = job.vendor_id, job.worker_id
        current.status = AssignmentStatus.RELEASED
        current.released_at = now
        # Release first so the single-active-assignment index never sees two rows.
        await self.session.flush()
        replacement = Assignment(
            job_id=job.id,
            vendor_id=vendor_id,
            worker_id=worker_id,
            status=AssignmentStatus.ACTIVE,
            assigned_by=actor_id,
        )
        self.session.add(replacement)
        job.vendor_id, job.worker_id = vendor_id, worker_id
        job.version += 1
        change = {
            "action": "reassigned",
            "previous_vendor_id": str(previous_vendor_id) if previous_vendor_id else None,
            "previous_worker_id": str(previous_worker_id) if previous_worker_id else None,
            "vendor_id": str(vendor_id),
            "worker_id": str(worker_id),
        }
        self.jobs.add_event(
            JobEvent(
                job_id=job.id,
                from_status=job.status,
                to_status=job.status,
                actor_id=actor_id,
                actor_type="operations",
                reason=reason,
                metadata_=change,
            )
        )
        self.session.add(
            AuditLog(
                actor_id=actor_id,
                action="assignment.reassign",
                resource_type="job",
                resource_id=job.id,
                metadata_json={
                    **change,
                    "released_assignment_id": str(current.id),
                    "reason": reason,
                },
                created_at=now,
            )
        )
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(409, "Job was reassigned concurrently") from exc
        await self.session.refresh(replacement)
        await self.session.refresh(job)
        return replacement, current, job
