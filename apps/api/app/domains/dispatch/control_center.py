"""Operations Control Center read models.

All projections are computed from PostgreSQL in one request-scoped session and
reuse the authoritative job lifecycle, dispatch rules, and SLA risk policy.
"""

import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal

from fastapi import HTTPException
from sqlalchemy import and_, distinct, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.booking.models import (
    Address,
    Booking,
    ProviderServiceCoverage,
    ProviderWorkingHours,
    ServiceArea,
)
from app.domains.catalog.models import Service
from app.domains.common.outbox import AuditLog, EventStatus, IntegrationEvent
from app.domains.geography.models import ServiceZonePostalCode
from app.domains.jobs.lifecycle import (
    ACTIVE_JOB_STATUSES,
    UNASSIGNED_JOB_STATUSES,
    operator_transitions,
    technician_commands,
)
from app.domains.jobs.models import Job, JobEvent, JobStatus, WorkRequest, WorkRequestStatus
from app.domains.jobs.repository import JobRepository
from app.domains.jobs.schemas import WorkRequestRead
from app.domains.workforce.models import Vendor, VendorStatus, Worker, WorkerStatus

from .models import Assignment, AssignmentStatus, DispatchOffer, OfferStatus
from .operations_schemas import (
    AssignmentCandidate,
    AssignmentCandidates,
    AssignmentHistoryRead,
    BookingSummary,
    CapacityBoard,
    CapacityTotals,
    ExceptionQueue,
    IntegrationEventSummary,
    IntegrationFailurePage,
    IntegrationHealthSummary,
    JobActions,
    JobControlDetail,
    JobDiagnostics,
    JobLocationSummary,
    OfferHistoryRead,
    OperationsDashboard,
    PartySummary,
    QueueItem,
    QueuePage,
    RiskCodeCount,
    RiskPolicyRead,
    RiskRead,
    ServiceAreaOperations,
    ServiceAreaProjection,
    SeverityCount,
    StatusCount,
    TimelineEntry,
    WorkerCapacity,
    WorkforceSummary,
)
from .risk import (
    DEFAULT_RISK_POLICY,
    SEVERITY_RANK,
    JobRiskSnapshot,
    RiskPolicy,
    RiskSeverity,
    evaluate_job_risks,
    highest_severity,
)
from .service import ASSIGNABLE_JOB_STATUSES, REASSIGNABLE_JOB_STATUSES, reserved_slot_conflict

INTEGRATION_FAILURE_STATUSES = (
    EventStatus.PENDING_CONFIGURATION,
    EventStatus.FAILED_TERMINAL,
    EventStatus.FAILED,
    EventStatus.DEAD_LETTER,
)
INTEGRATION_RETRYING_STATUSES = (EventStatus.RETRYING, EventStatus.FAILED_RETRYABLE)
RISK_SCAN_LIMIT = 1000
CAPACITY_WORKER_LIMIT = 500
SERVICE_AREA_LIMIT = 500
CANDIDATE_LIMIT = 200
SERVICE_AREA_PRIVACY_NOTE = (
    "Aggregate counts per BREERO service zone only. No street addresses, coordinates, "
    "boundaries, or customer identifiers are included."
)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _minutes(value: timedelta) -> int:
    return int(value.total_seconds() // 60)


@dataclass(frozen=True)
class QueueFilters:
    statuses: tuple[JobStatus, ...] = ()
    vendor_id: uuid.UUID | None = None
    worker_id: uuid.UUID | None = None
    service_id: uuid.UUID | None = None
    service_area_id: uuid.UUID | None = None
    unassigned_only: bool = False
    scheduled_from: datetime | None = None
    scheduled_to: datetime | None = None
    at_risk_only: bool = False
    severity: RiskSeverity | None = None


class OperationsControlCenterService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        policy: RiskPolicy = DEFAULT_RISK_POLICY,
        now: datetime | None = None,
    ) -> None:
        self.session = session
        self.policy = policy
        self.now = _aware(now) if now else datetime.now(UTC)

    # ------------------------------------------------------------------ queue rows

    def _job_rows(self):
        live_offers = (
            select(
                DispatchOffer.job_id.label("job_id"),
                func.count(DispatchOffer.id).label("live_offers"),
            )
            .where(
                DispatchOffer.status == OfferStatus.PENDING,
                DispatchOffer.expires_at > self.now,
            )
            .group_by(DispatchOffer.job_id)
            .subquery("live_offers")
        )
        unreviewed = (
            select(
                WorkRequest.job_id.label("job_id"),
                func.count(WorkRequest.id).label("unreviewed"),
                func.min(WorkRequest.created_at).label("oldest_unreviewed"),
            )
            .where(WorkRequest.status == WorkRequestStatus.SUBMITTED)
            .group_by(WorkRequest.job_id)
            .subquery("unreviewed")
        )
        last_event = (
            select(
                JobEvent.job_id.label("job_id"),
                func.max(JobEvent.created_at).label("last_event_at"),
            )
            .group_by(JobEvent.job_id)
            .subquery("last_event")
        )
        return (
            select(
                Job,
                Service.name.label("service_name"),
                Vendor.display_name.label("vendor_name"),
                Vendor.status.label("vendor_status"),
                Worker.first_name.label("worker_first_name"),
                Worker.last_name.label("worker_last_name"),
                Worker.status.label("worker_status"),
                Worker.available.label("worker_available"),
                Address.city.label("city"),
                Address.state_code.label("state_code"),
                Address.postal_code.label("postal_code"),
                Address.country_code.label("country_code"),
                Address.timezone_name.label("timezone_name"),
                Address.service_area_id.label("service_area_id"),
                ServiceArea.name.label("service_area_name"),
                func.coalesce(live_offers.c.live_offers, 0).label("live_offers"),
                func.coalesce(unreviewed.c.unreviewed, 0).label("unreviewed"),
                unreviewed.c.oldest_unreviewed.label("oldest_unreviewed"),
                last_event.c.last_event_at.label("last_event_at"),
            )
            .select_from(Job)
            .outerjoin(Service, Service.id == Job.service_id)
            .outerjoin(Vendor, Vendor.id == Job.vendor_id)
            .outerjoin(Worker, Worker.id == Job.worker_id)
            .outerjoin(Address, Address.id == Job.address_id)
            .outerjoin(ServiceArea, ServiceArea.id == Address.service_area_id)
            .outerjoin(live_offers, live_offers.c.job_id == Job.id)
            .outerjoin(unreviewed, unreviewed.c.job_id == Job.id)
            .outerjoin(last_event, last_event.c.job_id == Job.id)
        )

    @staticmethod
    def _conditions(filters: QueueFilters) -> list[Any]:
        conditions: list[Any] = []
        if filters.statuses:
            conditions.append(Job.status.in_(filters.statuses))
        else:
            conditions.append(Job.status.in_(ACTIVE_JOB_STATUSES))
        if filters.unassigned_only:
            conditions.append(Job.status.in_(UNASSIGNED_JOB_STATUSES))
        if filters.vendor_id:
            conditions.append(Job.vendor_id == filters.vendor_id)
        if filters.worker_id:
            conditions.append(Job.worker_id == filters.worker_id)
        if filters.service_id:
            conditions.append(Job.service_id == filters.service_id)
        if filters.service_area_id:
            conditions.append(Address.service_area_id == filters.service_area_id)
        if filters.scheduled_from:
            conditions.append(Job.scheduled_start >= filters.scheduled_from)
        if filters.scheduled_to:
            conditions.append(Job.scheduled_start < filters.scheduled_to)
        return conditions

    def _item(self, row: Any) -> QueueItem:
        job: Job = row.Job
        worker_dispatchable = bool(
            row.worker_status == WorkerStatus.ACTIVE
            and row.worker_available
            and row.vendor_status == VendorStatus.ACTIVE
        )
        last_changed_at = _aware(row.last_event_at or job.updated_at or job.created_at)
        oldest = row.oldest_unreviewed
        risks = evaluate_job_risks(
            JobRiskSnapshot(
                status=job.status,
                scheduled_start=_aware(job.scheduled_start),
                scheduled_end=_aware(job.scheduled_end),
                last_changed_at=last_changed_at,
                live_offer_count=int(row.live_offers),
                oldest_unreviewed_work_request_at=_aware(oldest) if oldest else None,
                has_worker=job.worker_id is not None,
                worker_dispatchable=worker_dispatchable,
            ),
            self.now,
            self.policy,
        )
        vendor = (
            PartySummary(
                id=job.vendor_id,
                name=row.vendor_name,
                status=row.vendor_status.value,
            )
            if job.vendor_id and row.vendor_name is not None
            else None
        )
        worker = (
            PartySummary(
                id=job.worker_id,
                name=f"{row.worker_first_name} {row.worker_last_name}".strip(),
                status=row.worker_status.value,
                available=bool(row.worker_available),
            )
            if job.worker_id and row.worker_status is not None
            else None
        )
        return QueueItem(
            job_id=job.id,
            booking_id=job.booking_id,
            status=job.status,
            version=job.version,
            scheduled_start=_aware(job.scheduled_start),
            scheduled_end=_aware(job.scheduled_end),
            service_id=job.service_id,
            service_name=row.service_name,
            location=JobLocationSummary(
                city=row.city,
                state_code=row.state_code,
                postal_code=row.postal_code,
                country_code=row.country_code,
                timezone_name=row.timezone_name,
                service_area_id=row.service_area_id,
                service_area_name=row.service_area_name,
            ),
            vendor=vendor,
            worker=worker,
            live_offer_count=int(row.live_offers),
            unreviewed_work_request_count=int(row.unreviewed),
            last_changed_at=last_changed_at,
            risks=[RiskRead(code=r.code, severity=r.severity, detail=r.detail) for r in risks],
            highest_severity=highest_severity(risks),
        )

    async def _scan(self, filters: QueueFilters) -> tuple[list[QueueItem], int, bool]:
        """Evaluate risk for up to RISK_SCAN_LIMIT matching jobs, earliest start first."""
        rows = (
            await self.session.execute(
                self._job_rows()
                .where(*self._conditions(filters))
                .order_by(Job.scheduled_start, Job.id)
                .limit(RISK_SCAN_LIMIT + 1)
            )
        ).all()
        truncated = len(rows) > RISK_SCAN_LIMIT
        items = [self._item(row) for row in rows[:RISK_SCAN_LIMIT]]
        return items, min(len(rows), RISK_SCAN_LIMIT), truncated

    @staticmethod
    def _matches_risk(item: QueueItem, severity: RiskSeverity | None) -> bool:
        if not item.risks:
            return False
        return severity is None or any(risk.severity == severity for risk in item.risks)

    @staticmethod
    def _risk_order(item: QueueItem) -> tuple[int, datetime]:
        rank = SEVERITY_RANK[item.highest_severity] if item.highest_severity else len(SEVERITY_RANK)
        return rank, item.scheduled_start

    # ------------------------------------------------------------------ public reads

    async def queue(self, filters: QueueFilters, *, limit: int, offset: int) -> QueuePage:
        if filters.at_risk_only or filters.severity:
            scanned, _, truncated = await self._scan(filters)
            matching = sorted(
                (item for item in scanned if self._matches_risk(item, filters.severity)),
                key=self._risk_order,
            )
            return QueuePage(
                generated_at=self.now,
                items=matching[offset : offset + limit],
                total=len(matching),
                limit=limit,
                offset=offset,
                scan_truncated=truncated,
            )

        conditions = self._conditions(filters)
        total = await self.session.scalar(
            select(func.count(Job.id))
            .select_from(Job)
            .outerjoin(Address, Address.id == Job.address_id)
            .where(*conditions)
        )
        rows = (
            await self.session.execute(
                self._job_rows()
                .where(*conditions)
                .order_by(Job.scheduled_start, Job.id)
                .limit(limit)
                .offset(offset)
            )
        ).all()
        return QueuePage(
            generated_at=self.now,
            items=[self._item(row) for row in rows],
            total=int(total or 0),
            limit=limit,
            offset=offset,
            scan_truncated=False,
        )

    def _policy_read(self) -> RiskPolicyRead:
        return RiskPolicyRead(
            unassigned_lead_time_minutes=_minutes(self.policy.unassigned_lead_time),
            approval_stall_after_minutes=_minutes(self.policy.approval_stall_after),
            work_request_review_after_minutes=_minutes(self.policy.work_request_review_after),
        )

    async def exceptions(self, severity: RiskSeverity | None = None) -> ExceptionQueue:
        scanned, scanned_count, truncated = await self._scan(QueueFilters())
        at_risk = sorted(
            (item for item in scanned if self._matches_risk(item, severity)),
            key=self._risk_order,
        )
        severity_counts = Counter(
            item.highest_severity for item in at_risk if item.highest_severity
        )
        code_counts = Counter(risk.code for item in at_risk for risk in item.risks)
        return ExceptionQueue(
            generated_at=self.now,
            policy=self._policy_read(),
            items=at_risk,
            by_severity=[
                SeverityCount(severity=level, count=severity_counts.get(level, 0))
                for level in RiskSeverity
            ],
            by_code=[
                RiskCodeCount(code=code, count=count)
                for code, count in sorted(code_counts.items(), key=lambda pair: pair[0].value)
            ],
            scanned_jobs=scanned_count,
            scan_truncated=truncated,
        )

    async def dashboard(self) -> OperationsDashboard:
        status_rows = (
            await self.session.execute(
                select(Job.status, func.count(Job.id)).group_by(Job.status)
            )
        ).all()
        by_status: dict[JobStatus, int] = {status: int(count) for status, count in status_rows}
        scheduled_next_24h = await self.session.scalar(
            select(func.count(Job.id)).where(
                Job.status.in_(ACTIVE_JOB_STATUSES),
                Job.scheduled_start >= self.now,
                Job.scheduled_start < self.now + timedelta(hours=24),
            )
        )
        live_offers = await self.session.scalar(
            select(func.count(DispatchOffer.id)).where(
                DispatchOffer.status == OfferStatus.PENDING,
                DispatchOffer.expires_at > self.now,
            )
        )
        work_request_rows = (
            await self.session.execute(
                select(WorkRequest.status, func.count(WorkRequest.id))
                .where(
                    WorkRequest.status.in_(
                        [WorkRequestStatus.SUBMITTED, WorkRequestStatus.PENDING_CUSTOMER]
                    )
                )
                .group_by(WorkRequest.status)
            )
        ).all()
        work_requests: dict[WorkRequestStatus, int] = {
            status: int(count) for status, count in work_request_rows
        }
        active_vendors = await self.session.scalar(
            select(func.count(Vendor.id)).where(Vendor.status == VendorStatus.ACTIVE)
        )
        active_workers_query = (
            select(func.count(Worker.id))
            .join(Vendor, Vendor.id == Worker.vendor_id)
            .where(Worker.status == WorkerStatus.ACTIVE, Vendor.status == VendorStatus.ACTIVE)
        )
        active_workers = await self.session.scalar(active_workers_query)
        dispatchable_workers = await self.session.scalar(
            active_workers_query.where(Worker.available.is_(True))
        )
        failed = await self.session.scalar(
            select(func.count(IntegrationEvent.id)).where(
                IntegrationEvent.status.in_(INTEGRATION_FAILURE_STATUSES)
            )
        )
        retrying = await self.session.scalar(
            select(func.count(IntegrationEvent.id)).where(
                IntegrationEvent.status.in_(INTEGRATION_RETRYING_STATUSES)
            )
        )
        exceptions = await self.exceptions()
        return OperationsDashboard(
            generated_at=self.now,
            jobs_by_status=[
                StatusCount(status=status, count=by_status.get(status, 0)) for status in JobStatus
            ],
            active_jobs=sum(by_status.get(status, 0) for status in ACTIVE_JOB_STATUSES),
            unassigned_jobs=sum(by_status.get(status, 0) for status in UNASSIGNED_JOB_STATUSES),
            scheduled_next_24h=int(scheduled_next_24h or 0),
            live_offers=int(live_offers or 0),
            work_requests_awaiting_review=work_requests.get(WorkRequestStatus.SUBMITTED, 0),
            work_requests_awaiting_customer=work_requests.get(
                WorkRequestStatus.PENDING_CUSTOMER, 0
            ),
            risk_by_severity=exceptions.by_severity,
            at_risk_jobs=len(exceptions.items),
            risk_scan_truncated=exceptions.scan_truncated,
            workforce=WorkforceSummary(
                active_vendors=int(active_vendors or 0),
                active_workers=int(active_workers or 0),
                dispatchable_workers=int(dispatchable_workers or 0),
            ),
            integrations=IntegrationHealthSummary(
                failed=int(failed or 0), retrying=int(retrying or 0)
            ),
        )

    async def capacity(
        self,
        day: date,
        *,
        vendor_id: uuid.UUID | None = None,
        include_inactive: bool = False,
    ) -> CapacityBoard:
        window_start = datetime.combine(day, time.min, tzinfo=UTC)
        window_end = window_start + timedelta(days=1)
        weekday = day.weekday()
        hours = (
            select(
                ProviderWorkingHours.worker_id.label("worker_id"),
                ProviderWorkingHours.start_time.label("start_time"),
                ProviderWorkingHours.end_time.label("end_time"),
                ProviderWorkingHours.capacity.label("capacity"),
            )
            .where(ProviderWorkingHours.weekday == weekday)
            .subquery("hours")
        )
        window_jobs = (
            select(Job.worker_id.label("worker_id"), func.count(Job.id).label("jobs"))
            .where(
                Job.worker_id.is_not(None),
                Job.status != JobStatus.CANCELLED,
                Job.scheduled_start >= window_start,
                Job.scheduled_start < window_end,
            )
            .group_by(Job.worker_id)
            .subquery("window_jobs")
        )
        active_jobs = (
            select(Job.worker_id.label("worker_id"), func.count(Job.id).label("jobs"))
            .where(Job.worker_id.is_not(None), Job.status.in_(ACTIVE_JOB_STATUSES))
            .group_by(Job.worker_id)
            .subquery("active_jobs")
        )
        coverage = (
            select(
                ProviderServiceCoverage.worker_id.label("worker_id"),
                func.count(distinct(ProviderServiceCoverage.postal_code)).label("postal_codes"),
                func.count(distinct(ProviderServiceCoverage.service_id)).label("services"),
            )
            .where(ProviderServiceCoverage.active.is_(True))
            .group_by(ProviderServiceCoverage.worker_id)
            .subquery("coverage")
        )
        query = (
            select(
                Worker,
                Vendor.display_name.label("vendor_name"),
                Vendor.status.label("vendor_status"),
                hours.c.start_time,
                hours.c.end_time,
                func.coalesce(hours.c.capacity, 0).label("capacity"),
                func.coalesce(window_jobs.c.jobs, 0).label("window_jobs"),
                func.coalesce(active_jobs.c.jobs, 0).label("active_jobs"),
                func.coalesce(coverage.c.postal_codes, 0).label("postal_codes"),
                func.coalesce(coverage.c.services, 0).label("services"),
            )
            .join(Vendor, Vendor.id == Worker.vendor_id)
            .outerjoin(hours, hours.c.worker_id == Worker.id)
            .outerjoin(window_jobs, window_jobs.c.worker_id == Worker.id)
            .outerjoin(active_jobs, active_jobs.c.worker_id == Worker.id)
            .outerjoin(coverage, coverage.c.worker_id == Worker.id)
            .order_by(Vendor.display_name, Worker.last_name, Worker.first_name, Worker.id)
            .limit(CAPACITY_WORKER_LIMIT + 1)
        )
        if vendor_id:
            query = query.where(Worker.vendor_id == vendor_id)
        if not include_inactive:
            query = query.where(
                Worker.status == WorkerStatus.ACTIVE, Vendor.status == VendorStatus.ACTIVE
            )
        rows = (await self.session.execute(query)).all()
        truncated = len(rows) > CAPACITY_WORKER_LIMIT
        workers: list[WorkerCapacity] = []
        for row in rows[:CAPACITY_WORKER_LIMIT]:
            worker: Worker = row.Worker
            capacity = int(row.capacity)
            scheduled = int(row.window_jobs)
            workers.append(
                WorkerCapacity(
                    worker_id=worker.id,
                    worker_name=f"{worker.first_name} {worker.last_name}".strip(),
                    worker_status=worker.status,
                    available=bool(worker.available),
                    vendor_id=worker.vendor_id,
                    vendor_name=row.vendor_name,
                    vendor_status=row.vendor_status,
                    shift_start=row.start_time.strftime("%H:%M") if row.start_time else None,
                    shift_end=row.end_time.strftime("%H:%M") if row.end_time else None,
                    daily_capacity=capacity,
                    jobs_in_window=scheduled,
                    active_jobs=int(row.active_jobs),
                    covered_postal_codes=int(row.postal_codes),
                    covered_services=int(row.services),
                    utilization_percent=round(scheduled * 100 / capacity) if capacity else None,
                    over_capacity=scheduled > capacity,
                )
            )
        return CapacityBoard(
            generated_at=self.now,
            date=day,
            weekday=weekday,
            window_start=window_start,
            window_end=window_end,
            workers=workers,
            totals=CapacityTotals(
                workers=len(workers),
                daily_capacity=sum(item.daily_capacity for item in workers),
                jobs_in_window=sum(item.jobs_in_window for item in workers),
                workers_without_hours=sum(1 for item in workers if item.shift_start is None),
                workers_over_capacity=sum(1 for item in workers if item.over_capacity),
            ),
            truncated=truncated,
        )

    async def service_areas(self) -> ServiceAreaProjection:
        postal_codes = (
            select(
                ServiceZonePostalCode.service_area_id.label("area_id"),
                func.count(ServiceZonePostalCode.id).label("postal_codes"),
            )
            .where(ServiceZonePostalCode.active.is_(True))
            .group_by(ServiceZonePostalCode.service_area_id)
            .subquery("zone_postal_codes")
        )
        area_jobs = (
            select(
                Address.service_area_id.label("area_id"),
                func.count(Job.id).label("active_jobs"),
                func.count(Job.id)
                .filter(Job.status.in_(UNASSIGNED_JOB_STATUSES))
                .label("unassigned_jobs"),
            )
            .select_from(Job)
            .join(Address, Address.id == Job.address_id)
            .where(Job.status.in_(ACTIVE_JOB_STATUSES), Address.service_area_id.is_not(None))
            .group_by(Address.service_area_id)
            .subquery("area_jobs")
        )
        covering = (
            select(
                ServiceZonePostalCode.service_area_id.label("area_id"),
                func.count(distinct(ProviderServiceCoverage.worker_id)).label("workers"),
            )
            .select_from(ServiceZonePostalCode)
            .join(
                ProviderServiceCoverage,
                and_(
                    ProviderServiceCoverage.postal_code
                    == func.substr(ServiceZonePostalCode.postal_code, 1, 5),
                    ProviderServiceCoverage.active.is_(True),
                ),
            )
            .join(Worker, Worker.id == ProviderServiceCoverage.worker_id)
            .join(Vendor, Vendor.id == Worker.vendor_id)
            .where(
                ServiceZonePostalCode.active.is_(True),
                Worker.status == WorkerStatus.ACTIVE,
                Worker.available.is_(True),
                Vendor.status == VendorStatus.ACTIVE,
            )
            .group_by(ServiceZonePostalCode.service_area_id)
            .subquery("covering_workers")
        )
        rows = (
            await self.session.execute(
                select(
                    ServiceArea.id,
                    ServiceArea.name,
                    ServiceArea.country_code,
                    ServiceArea.state_code,
                    ServiceArea.city,
                    ServiceArea.active,
                    ServiceArea.emergency_enabled,
                    func.coalesce(postal_codes.c.postal_codes, 0).label("postal_codes"),
                    func.coalesce(area_jobs.c.active_jobs, 0).label("active_jobs"),
                    func.coalesce(area_jobs.c.unassigned_jobs, 0).label("unassigned_jobs"),
                    func.coalesce(covering.c.workers, 0).label("workers"),
                )
                .outerjoin(postal_codes, postal_codes.c.area_id == ServiceArea.id)
                .outerjoin(area_jobs, area_jobs.c.area_id == ServiceArea.id)
                .outerjoin(covering, covering.c.area_id == ServiceArea.id)
                .order_by(ServiceArea.active.desc(), ServiceArea.priority, ServiceArea.name)
                .limit(SERVICE_AREA_LIMIT)
            )
        ).all()
        unzoned = await self.session.scalar(
            select(func.count(Job.id))
            .select_from(Job)
            .outerjoin(Address, Address.id == Job.address_id)
            .where(
                Job.status.in_(ACTIVE_JOB_STATUSES),
                or_(Address.id.is_(None), Address.service_area_id.is_(None)),
            )
        )
        return ServiceAreaProjection(
            generated_at=self.now,
            areas=[
                ServiceAreaOperations(
                    service_area_id=row.id,
                    name=row.name,
                    country_code=row.country_code,
                    state_code=row.state_code,
                    city=row.city,
                    active=bool(row.active),
                    emergency_enabled=bool(row.emergency_enabled),
                    postal_code_count=int(row.postal_codes),
                    active_jobs=int(row.active_jobs),
                    unassigned_jobs=int(row.unassigned_jobs),
                    covering_dispatchable_workers=int(row.workers),
                )
                for row in rows
            ],
            unzoned_active_jobs=int(unzoned or 0),
            privacy=SERVICE_AREA_PRIVACY_NOTE,
        )

    async def integration_failures(
        self, *, limit: int, retry_permitted: bool
    ) -> IntegrationFailurePage:
        events = (
            await self.session.scalars(
                select(IntegrationEvent)
                .where(IntegrationEvent.status.in_(INTEGRATION_FAILURE_STATUSES))
                .order_by(IntegrationEvent.created_at.desc())
                .limit(limit)
            )
        ).all()
        return IntegrationFailurePage(
            generated_at=self.now,
            items=[IntegrationEventSummary.model_validate(event) for event in events],
            retry_permitted=retry_permitted,
        )

    # ------------------------------------------------------------------ job detail

    async def _queue_item(self, job_id: uuid.UUID) -> QueueItem:
        row = (await self.session.execute(self._job_rows().where(Job.id == job_id))).first()
        if row is None:
            raise HTTPException(404, "Job not found")
        return self._item(row)

    async def job_detail(self, job_id: uuid.UUID) -> JobControlDetail:
        item = await self._queue_item(job_id)
        job = await JobRepository(self.session).get(job_id)
        if job is None:
            raise HTTPException(404, "Job not found")
        booking = await self.session.get(Booking, job.booking_id)
        assignments = (
            await self.session.scalars(
                select(Assignment)
                .where(Assignment.job_id == job_id)
                .order_by(Assignment.assigned_at, Assignment.id)
            )
        ).all()
        offers = (
            await self.session.scalars(
                select(DispatchOffer)
                .where(DispatchOffer.job_id == job_id)
                .order_by(DispatchOffer.round.desc(), DispatchOffer.score.desc())
            )
        ).all()
        work_requests = await JobRepository(self.session).list_work_requests(job_id)
        events = (
            await self.session.scalars(
                select(JobEvent)
                .where(JobEvent.job_id == job_id)
                .order_by(JobEvent.created_at, JobEvent.id)
            )
        ).all()
        audit_scopes = [and_(AuditLog.resource_type == "job", AuditLog.resource_id == job_id)]
        if work_requests:
            audit_scopes.append(
                and_(
                    AuditLog.resource_type == "work_request",
                    AuditLog.resource_id.in_([request.id for request in work_requests]),
                )
            )
        if booking is not None:
            audit_scopes.append(
                and_(AuditLog.resource_type == "booking", AuditLog.resource_id == booking.id)
            )
        audits = (
            await self.session.scalars(
                select(AuditLog).where(or_(*audit_scopes)).order_by(AuditLog.created_at)
            )
        ).all()
        event_scopes = [
            and_(IntegrationEvent.aggregate_type == "job", IntegrationEvent.aggregate_id == job_id)
        ]
        if booking is not None:
            event_scopes.append(
                and_(
                    IntegrationEvent.aggregate_type == "booking",
                    IntegrationEvent.aggregate_id == booking.id,
                )
            )
        integration_events = (
            await self.session.scalars(
                select(IntegrationEvent)
                .where(or_(*event_scopes))
                .order_by(IntegrationEvent.created_at.desc())
                .limit(50)
            )
        ).all()

        timeline = [
            TimelineEntry(
                kind="status",
                at=_aware(event.created_at),
                actor_id=event.actor_id,
                actor_type=event.actor_type,
                action=(event.metadata_ or {}).get("action", "transition"),
                from_status=event.from_status,
                to_status=event.to_status,
                reason=event.reason,
                metadata=event.metadata_ or {},
            )
            for event in events
        ] + [
            TimelineEntry(
                kind="audit",
                at=_aware(audit.created_at),
                actor_id=audit.actor_id,
                actor_type=audit.actor_type,
                action=audit.action,
                reason=(audit.metadata_json or {}).get("reason"),
                metadata=audit.metadata_json or {},
            )
            for audit in audits
        ]
        timeline.sort(key=lambda entry: entry.at)

        has_active_assignment = any(
            assignment.status == AssignmentStatus.ACTIVE for assignment in assignments
        )
        return JobControlDetail(
            generated_at=self.now,
            job=item,
            created_at=_aware(job.created_at),
            updated_at=_aware(job.updated_at),
            booking=(
                BookingSummary(
                    id=booking.id,
                    reference=booking.reference,
                    status=booking.status,
                    provider_worker_id=booking.provider_worker_id,
                    window_start=_aware(booking.window_start),
                    window_end=_aware(booking.window_end),
                )
                if booking is not None
                else None
            ),
            diagnostics=JobDiagnostics(
                diagnostic_notes=job.diagnostic_notes,
                completion_notes=job.completion_notes,
                completed_at=job.completed_at,
            ),
            assignments=[AssignmentHistoryRead.model_validate(a) for a in assignments],
            offers=[OfferHistoryRead.model_validate(o) for o in offers],
            timeline=timeline,
            work_requests=[WorkRequestRead.model_validate(r) for r in work_requests],
            integration_events=[
                IntegrationEventSummary.model_validate(e) for e in integration_events
            ],
            actions=JobActions(
                allowed_transitions=operator_transitions(job.status),
                technician_commands=technician_commands(job.status),
                can_match=job.status in ASSIGNABLE_JOB_STATUSES,
                can_assign=job.status in ASSIGNABLE_JOB_STATUSES,
                can_reassign=job.status in REASSIGNABLE_JOB_STATUSES and has_active_assignment,
                reviewable_work_request_ids=[
                    request.id
                    for request in work_requests
                    if request.status == WorkRequestStatus.SUBMITTED
                ],
            ),
        )

    async def assignment_candidates(self, job_id: uuid.UUID) -> AssignmentCandidates:
        job = await JobRepository(self.session).get(job_id)
        if job is None:
            raise HTTPException(404, "Job not found")
        booking = await self.session.get(Booking, job.booking_id)
        address = await self.session.get(Address, job.address_id)
        postal_code = address.postal_code[:5] if address and address.postal_code else None
        mode: Literal["assign", "reassign", "none"] = (
            "assign"
            if job.status in ASSIGNABLE_JOB_STATUSES
            else "reassign"
            if job.status in REASSIGNABLE_JOB_STATUSES
            else "none"
        )
        active_jobs = (
            select(Job.worker_id.label("worker_id"), func.count(Job.id).label("jobs"))
            .where(Job.worker_id.is_not(None), Job.status.in_(ACTIVE_JOB_STATUSES))
            .group_by(Job.worker_id)
            .subquery("active_jobs")
        )
        covers = (
            select(ProviderServiceCoverage.id)
            .where(
                ProviderServiceCoverage.worker_id == Worker.id,
                ProviderServiceCoverage.service_id == job.service_id,
                ProviderServiceCoverage.postal_code == postal_code,
                ProviderServiceCoverage.active.is_(True),
            )
            .exists()
            if postal_code
            else false()
        )
        rows = (
            await self.session.execute(
                select(
                    Worker,
                    Vendor.display_name.label("vendor_name"),
                    func.coalesce(active_jobs.c.jobs, 0).label("active_jobs"),
                    covers.label("covers"),
                )
                .join(Vendor, Vendor.id == Worker.vendor_id)
                .outerjoin(active_jobs, active_jobs.c.worker_id == Worker.id)
                .where(Worker.status == WorkerStatus.ACTIVE, Vendor.status == VendorStatus.ACTIVE)
                .order_by(Vendor.display_name, Worker.last_name, Worker.first_name, Worker.id)
                .limit(CANDIDATE_LIMIT)
            )
        ).all()
        candidates: list[AssignmentCandidate] = []
        for row in rows:
            worker: Worker = row.Worker
            currently_assigned = job.worker_id == worker.id
            holds_slot = booking is not None and booking.provider_worker_id == worker.id
            reasons: list[str] = []
            if mode == "none":
                reasons.append("JOB_NOT_ASSIGNABLE")
            if not worker.available:
                reasons.append("WORKER_UNAVAILABLE")
            if mode == "assign" and reserved_slot_conflict(booking, worker.id):
                reasons.append("RESERVED_FOR_ANOTHER_WORKER")
            if mode == "reassign" and currently_assigned:
                reasons.append("CURRENTLY_ASSIGNED")
            candidates.append(
                AssignmentCandidate(
                    worker_id=worker.id,
                    worker_name=f"{worker.first_name} {worker.last_name}".strip(),
                    vendor_id=worker.vendor_id,
                    vendor_name=row.vendor_name,
                    available=bool(worker.available),
                    holds_reserved_slot=holds_slot,
                    covers_job_postal_code=bool(row.covers),
                    active_jobs=int(row.active_jobs),
                    currently_assigned=currently_assigned,
                    eligible=not reasons,
                    blocking_reasons=reasons,
                )
            )
        candidates.sort(
            key=lambda c: (
                not c.eligible,
                not c.holds_reserved_slot,
                not c.covers_job_postal_code,
                c.active_jobs,
                c.worker_name,
            )
        )
        return AssignmentCandidates(
            generated_at=self.now,
            job_id=job.id,
            job_status=job.status,
            job_version=job.version,
            mode=mode,
            reserved_worker_id=booking.provider_worker_id if booking is not None else None,
            candidates=candidates,
        )
