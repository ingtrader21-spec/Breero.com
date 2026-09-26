"""Response contracts for the Operations Control Center read models.

Every projection is aggregate or operations-scoped: no street address lines,
coordinates, geometry, customer contact data, integration payloads, or raw
provider error text are exposed.
"""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.domains.booking.models import BookingStatus
from app.domains.common.outbox import EventStatus
from app.domains.jobs.models import JobStatus
from app.domains.jobs.schemas import WorkRequestRead
from app.domains.workforce.models import VendorStatus, WorkerStatus

from .models import AssignmentStatus, OfferStatus
from .risk import RiskCode, RiskSeverity


class RiskRead(BaseModel):
    code: RiskCode
    severity: RiskSeverity
    detail: str


class RiskPolicyRead(BaseModel):
    unassigned_lead_time_minutes: int
    approval_stall_after_minutes: int
    work_request_review_after_minutes: int


class JobLocationSummary(BaseModel):
    """Area-level location only; never the street line or coordinates."""

    city: str | None
    state_code: str | None
    postal_code: str | None
    country_code: str | None
    timezone_name: str | None
    service_area_id: uuid.UUID | None
    service_area_name: str | None


class PartySummary(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    available: bool | None = None


class QueueItem(BaseModel):
    job_id: uuid.UUID
    booking_id: uuid.UUID
    status: JobStatus
    version: int
    scheduled_start: datetime
    scheduled_end: datetime
    service_id: uuid.UUID
    service_name: str | None
    location: JobLocationSummary
    vendor: PartySummary | None
    worker: PartySummary | None
    live_offer_count: int
    unreviewed_work_request_count: int
    last_changed_at: datetime
    risks: list[RiskRead]
    highest_severity: RiskSeverity | None


class QueuePage(BaseModel):
    generated_at: datetime
    items: list[QueueItem]
    total: int
    limit: int
    offset: int
    scan_truncated: bool


class SeverityCount(BaseModel):
    severity: RiskSeverity
    count: int


class RiskCodeCount(BaseModel):
    code: RiskCode
    count: int


class ExceptionQueue(BaseModel):
    generated_at: datetime
    policy: RiskPolicyRead
    items: list[QueueItem]
    by_severity: list[SeverityCount]
    by_code: list[RiskCodeCount]
    scanned_jobs: int
    scan_truncated: bool


class StatusCount(BaseModel):
    status: JobStatus
    count: int


class WorkforceSummary(BaseModel):
    active_vendors: int
    active_workers: int
    dispatchable_workers: int


class IntegrationHealthSummary(BaseModel):
    failed: int
    retrying: int


class OperationsDashboard(BaseModel):
    generated_at: datetime
    jobs_by_status: list[StatusCount]
    active_jobs: int
    unassigned_jobs: int
    scheduled_next_24h: int
    live_offers: int
    work_requests_awaiting_review: int
    work_requests_awaiting_customer: int
    risk_by_severity: list[SeverityCount]
    at_risk_jobs: int
    risk_scan_truncated: bool
    workforce: WorkforceSummary
    integrations: IntegrationHealthSummary


class WorkerCapacity(BaseModel):
    worker_id: uuid.UUID
    worker_name: str
    worker_status: WorkerStatus
    available: bool
    vendor_id: uuid.UUID
    vendor_name: str
    vendor_status: VendorStatus
    shift_start: str | None
    shift_end: str | None
    daily_capacity: int
    jobs_in_window: int
    active_jobs: int
    covered_postal_codes: int
    covered_services: int
    utilization_percent: int | None
    over_capacity: bool


class CapacityTotals(BaseModel):
    workers: int
    daily_capacity: int
    jobs_in_window: int
    workers_without_hours: int
    workers_over_capacity: int


class CapacityBoard(BaseModel):
    generated_at: datetime
    date: date
    weekday: int
    window_start: datetime
    window_end: datetime
    workers: list[WorkerCapacity]
    totals: CapacityTotals
    truncated: bool


class ServiceAreaOperations(BaseModel):
    service_area_id: uuid.UUID | None
    name: str
    country_code: str | None
    state_code: str | None
    city: str | None
    active: bool
    emergency_enabled: bool
    postal_code_count: int
    active_jobs: int
    unassigned_jobs: int
    covering_dispatchable_workers: int


class ServiceAreaProjection(BaseModel):
    generated_at: datetime
    areas: list[ServiceAreaOperations]
    unzoned_active_jobs: int
    privacy: str


class IntegrationEventSummary(BaseModel):
    """Operations-safe outbox event view; payload and raw error text are withheld."""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    aggregate_type: str
    aggregate_id: uuid.UUID
    event_type: str
    status: EventStatus
    attempt_count: int
    last_error_code: str | None
    last_error_at: datetime | None
    next_attempt_at: datetime
    created_at: datetime


class IntegrationFailurePage(BaseModel):
    generated_at: datetime
    items: list[IntegrationEventSummary]
    retry_permitted: bool


class AssignmentHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    offer_id: uuid.UUID | None
    vendor_id: uuid.UUID
    worker_id: uuid.UUID
    status: AssignmentStatus
    assigned_by: uuid.UUID | None
    assigned_at: datetime
    released_at: datetime | None


class OfferHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    vendor_id: uuid.UUID
    worker_id: uuid.UUID | None
    status: OfferStatus
    round: int
    score: int
    expires_at: datetime
    responded_at: datetime | None
    created_at: datetime


class TimelineEntry(BaseModel):
    kind: str
    at: datetime
    actor_id: uuid.UUID | None
    actor_type: str | None
    action: str
    from_status: JobStatus | None = None
    to_status: JobStatus | None = None
    reason: str | None = None
    metadata: dict


class BookingSummary(BaseModel):
    id: uuid.UUID
    reference: str
    status: BookingStatus
    provider_worker_id: uuid.UUID | None
    window_start: datetime
    window_end: datetime


class JobActions(BaseModel):
    allowed_transitions: list[JobStatus]
    technician_commands: list[str]
    can_match: bool
    can_assign: bool
    can_reassign: bool
    reviewable_work_request_ids: list[uuid.UUID]


class JobDiagnostics(BaseModel):
    diagnostic_notes: str | None
    completion_notes: str | None
    completed_at: datetime | None


class JobControlDetail(BaseModel):
    generated_at: datetime
    job: QueueItem
    created_at: datetime
    updated_at: datetime
    booking: BookingSummary | None
    diagnostics: JobDiagnostics
    assignments: list[AssignmentHistoryRead]
    offers: list[OfferHistoryRead]
    timeline: list[TimelineEntry]
    work_requests: list[WorkRequestRead]
    integration_events: list[IntegrationEventSummary]
    actions: JobActions


class AssignmentCandidate(BaseModel):
    worker_id: uuid.UUID
    worker_name: str
    vendor_id: uuid.UUID
    vendor_name: str
    available: bool
    holds_reserved_slot: bool
    covers_job_postal_code: bool
    active_jobs: int
    currently_assigned: bool
    eligible: bool
    blocking_reasons: list[str]


class AssignmentCandidates(BaseModel):
    """Pre-screen only; the assign/reassign mutation remains the final authority."""

    generated_at: datetime
    job_id: uuid.UUID
    job_status: JobStatus
    job_version: int
    mode: Literal["assign", "reassign", "none"]
    reserved_worker_id: uuid.UUID | None
    candidates: list[AssignmentCandidate]
