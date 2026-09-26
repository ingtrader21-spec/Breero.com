import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.domains.booking.models import Booking
from app.domains.common.outbox import AuditLog, EventStatus, IntegrationEvent
from app.domains.finance.models import VendorEarning
from app.domains.finance.service import FinanceService

from .models import Job, JobEvent, JobStatus, WorkRequest, WorkRequestStatus
from .repository import JobRepository
from .schemas import WorkRequestCreate

TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.CREATED: {JobStatus.MATCHING, JobStatus.CANCELLED},
    JobStatus.MATCHING: {JobStatus.OFFERED, JobStatus.ASSIGNED, JobStatus.CANCELLED},
    JobStatus.OFFERED: {JobStatus.MATCHING, JobStatus.ASSIGNED, JobStatus.CANCELLED},
    JobStatus.ASSIGNED: {JobStatus.EN_ROUTE, JobStatus.CANCELLED},
    JobStatus.EN_ROUTE: {JobStatus.ON_SITE, JobStatus.CANCELLED},
    JobStatus.ON_SITE: {JobStatus.DIAGNOSING, JobStatus.IN_PROGRESS, JobStatus.CANCELLED},
    JobStatus.DIAGNOSING: {JobStatus.AWAITING_APPROVAL, JobStatus.IN_PROGRESS, JobStatus.CANCELLED},
    JobStatus.AWAITING_APPROVAL: {JobStatus.IN_PROGRESS, JobStatus.CANCELLED},
    JobStatus.IN_PROGRESS: {JobStatus.COMPLETED, JobStatus.AWAITING_APPROVAL, JobStatus.CANCELLED},
    JobStatus.COMPLETED: set(),
    JobStatus.CANCELLED: set(),
}

WORK_REQUEST_TRANSITIONS: dict[WorkRequestStatus, set[WorkRequestStatus]] = {
    WorkRequestStatus.DRAFT: {WorkRequestStatus.SUBMITTED},
    WorkRequestStatus.SUBMITTED: {
        WorkRequestStatus.PENDING_CUSTOMER,
        WorkRequestStatus.DECLINED,
    },
    WorkRequestStatus.PENDING_CUSTOMER: {
        WorkRequestStatus.APPROVED_PENDING_PAYMENT,
        WorkRequestStatus.DECLINED,
    },
    WorkRequestStatus.APPROVED_PENDING_PAYMENT: {WorkRequestStatus.APPROVED},
    WorkRequestStatus.APPROVED: set(),
    WorkRequestStatus.DECLINED: set(),
    WorkRequestStatus.PAID: set(),
    WorkRequestStatus.CANCELLED: set(),
    WorkRequestStatus.EXPIRED: set(),
}


class JobService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = JobRepository(session)

    def apply_transition(
        self,
        job: Job,
        target: JobStatus,
        actor_id: uuid.UUID | None,
        actor_type: str,
        reason: str | None = None,
        metadata: dict | None = None,
    ) -> bool:
        """Apply the single authoritative in-transaction job transition."""
        if target == job.status:
            return False
        if target not in TRANSITIONS[job.status]:
            raise HTTPException(
                409, f"Cannot transition job from {job.status.value} to {target.value}"
            )
        if target == JobStatus.COMPLETED:
            self._validate_completion(job)
        previous = job.status
        job.status = target
        job.version += 1
        if target == JobStatus.COMPLETED:
            job.completed_at = datetime.now(UTC)
        self.repo.add_event(
            JobEvent(
                job_id=job.id,
                from_status=previous,
                to_status=target,
                actor_id=actor_id,
                actor_type=actor_type,
                reason=reason,
                metadata_=metadata or {},
            )
        )
        return True

    @staticmethod
    def apply_work_request_transition(
        request: WorkRequest, target: WorkRequestStatus
    ) -> bool:
        """Apply the authoritative work-request lifecycle transition."""
        if request.status == target:
            return False
        if target not in WORK_REQUEST_TRANSITIONS[request.status]:
            raise HTTPException(
                409,
                f"Cannot transition work request from {request.status.value} to {target.value}",
            )
        request.status = target
        return True

    async def transition_locked(
        self,
        job_id: uuid.UUID,
        target: JobStatus,
        actor_id: uuid.UUID | None,
        actor_type: str,
        reason: str | None = None,
    ) -> Job:
        job = await self.repo.get(job_id, lock=True)
        if not job:
            raise HTTPException(404, "Job not found")
        changed = self.apply_transition(job, target, actor_id, actor_type, reason)
        if changed and target == JobStatus.COMPLETED:
            await self._record_completion_effects(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def transition(
        self,
        job_id: uuid.UUID,
        target: JobStatus,
        actor_id: uuid.UUID | None,
        actor_type: str,
        reason: str | None = None,
    ) -> Job:
        return await self.transition_locked(job_id, target, actor_id, actor_type, reason)

    async def technician_note_transition(
        self,
        job_id: uuid.UUID,
        worker_id: uuid.UUID,
        actor_id: uuid.UUID,
        notes_field: str,
        notes: str,
        target: JobStatus,
    ) -> Job:
        job = await self.repo.get(job_id, lock=True)
        if not job or job.worker_id != worker_id:
            raise HTTPException(403, "Technician is not assigned to this job")
        setattr(job, notes_field, notes)
        changed = self.apply_transition(
            job, target, actor_id, "worker", f"{notes_field}_recorded"
        )
        if changed and target == JobStatus.COMPLETED:
            await self._record_completion_effects(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    @staticmethod
    def _validate_completion(job: Job) -> None:
        if not job.vendor_id or not job.worker_id:
            raise HTTPException(409, "Job must be assigned before completion")
        if not job.diagnostic_notes or not job.completion_notes:
            raise HTTPException(409, "Diagnostic and completion notes are required")

    async def _record_completion_effects(self, job: Job) -> None:
        existing = await self.session.scalar(
            select(VendorEarning).where(VendorEarning.job_id == job.id)
        )
        if settings.payout_enabled and not existing:
            booking = await self.session.get(Booking, job.booking_id)
            if not booking:
                raise HTTPException(409, "Job booking is unavailable")
            gross = int(booking.total_amount * 100)
            await FinanceService(self.session).recognize_earning(
                job, gross_minor=gross, currency=booking.currency
            )
        self.session.add(
            IntegrationEvent(
                aggregate_type="job",
                aggregate_id=job.id,
                event_type="job.completed",
                payload={"job_id": str(job.id), "vendor_id": str(job.vendor_id)},
                status=EventStatus.PENDING,
                attempts=0,
                available_at=datetime.now(UTC),
            )
        )

    async def create_work_request(
        self, job_id: uuid.UUID, payload: WorkRequestCreate, worker_id: uuid.UUID
    ) -> WorkRequest:
        job = await self.repo.get(job_id, lock=True)
        if not job:
            raise HTTPException(404, "Job not found")
        if job.worker_id != worker_id:
            raise HTTPException(403, "Worker is not assigned to this job")
        if job.status not in {JobStatus.ON_SITE, JobStatus.DIAGNOSING, JobStatus.IN_PROGRESS}:
            raise HTTPException(409, "Additional work cannot be requested in the current job state")
        items = [item.model_dump() for item in payload.line_items]
        subtotal = sum(item.quantity * item.unit_price_minor for item in payload.line_items)
        request = WorkRequest(
            job_id=job.id,
            status=WorkRequestStatus.SUBMITTED,
            description=payload.description,
            line_items=items,
            subtotal_minor=subtotal,
            tax_minor=payload.tax_minor,
            total_minor=subtotal + payload.tax_minor,
            currency=payload.currency,
            created_by=worker_id,
        )
        self.session.add(request)
        self.apply_transition(
            job, JobStatus.AWAITING_APPROVAL, worker_id, "worker", "additional_work_requested"
        )
        await self.session.commit()
        await self.session.refresh(request)
        return request

    async def decide_work_request(
        self, request_id: uuid.UUID, approve: bool, customer_id: uuid.UUID
    ) -> WorkRequest:
        request = await self.repo.get_work_request(request_id, lock=True)
        if not request:
            raise HTTPException(404, "Work request not found")
        job = await self.repo.get(request.job_id, lock=True)
        if not job or job.customer_id != customer_id:
            raise HTTPException(403, "Not permitted to decide this request")
        if request.status != WorkRequestStatus.PENDING_CUSTOMER:
            raise HTTPException(409, "Work request has already been decided")
        target = WorkRequestStatus.DECLINED
        if approve:
            target = (
                WorkRequestStatus.APPROVED_PENDING_PAYMENT
                if settings.payments_enabled
                else WorkRequestStatus.APPROVED
            )
        if target == WorkRequestStatus.APPROVED:
            request.status = target
        else:
            self.apply_work_request_transition(request, target)
        request.customer_decided_at = datetime.now(UTC)
        self.session.add(
            AuditLog(
                actor_id=customer_id,
                action="quote.approve" if approve else "quote.reject",
                resource_type="work_request",
                resource_id=request.id,
                metadata_json={
                    "previous_status": WorkRequestStatus.PENDING_CUSTOMER.value,
                    "new_status": request.status.value,
                    "payment_required": approve and settings.payments_enabled,
                },
                created_at=datetime.now(UTC),
            )
        )
        if not approve:
            self.apply_transition(
                job, JobStatus.IN_PROGRESS, customer_id, "customer", "additional_work_declined"
            )
        elif not settings.payments_enabled:
            self.apply_transition(
                job, JobStatus.IN_PROGRESS, customer_id, "customer", "quote_approved_no_payment"
            )
        await self.session.commit()
        await self.session.refresh(request)
        return request

    async def review_work_request(
        self, request_id: uuid.UUID, approve: bool, actor_id: uuid.UUID | None = None
    ) -> WorkRequest:
        request = await self.repo.get_work_request(request_id, lock=True)
        if not request:
            raise HTTPException(404, "Work request not found")
        if request.status != WorkRequestStatus.SUBMITTED:
            raise HTTPException(409, "Work request has already been reviewed")
        self.apply_work_request_transition(
            request,
            WorkRequestStatus.PENDING_CUSTOMER if approve else WorkRequestStatus.DECLINED,
        )
        self.session.add(
            AuditLog(
                actor_id=actor_id,
                action="work_request.review",
                resource_type="work_request",
                resource_id=request.id,
                metadata_json={
                    "job_id": str(request.job_id),
                    "previous_status": WorkRequestStatus.SUBMITTED.value,
                    "new_status": request.status.value,
                },
                created_at=datetime.now(UTC),
            )
        )
        if not approve:
            job = await self.repo.get(request.job_id, lock=True)
            if job and job.status == JobStatus.AWAITING_APPROVAL:
                self.apply_transition(
                    job,
                    JobStatus.IN_PROGRESS,
                    actor_id,
                    "operations",
                    "work_request_rejected",
                )
        await self.session.commit()
        await self.session.refresh(request)
        return request
