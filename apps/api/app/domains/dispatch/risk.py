"""Operations SLA / exception policy.

This is the single place where "at risk" is defined. Read models evaluate it on
PostgreSQL-sourced snapshots and return both the findings and the thresholds,
so operations screens display server truth instead of computing their own.
"""

import enum
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.domains.jobs.lifecycle import (
    ASSIGNED_WORK_STATUSES,
    FIELD_EXECUTION_STATUSES,
    UNASSIGNED_JOB_STATUSES,
)
from app.domains.jobs.models import JobStatus


class RiskSeverity(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"


SEVERITY_RANK: dict[RiskSeverity, int] = {
    RiskSeverity.CRITICAL: 0,
    RiskSeverity.HIGH: 1,
    RiskSeverity.MEDIUM: 2,
}


class RiskCode(str, enum.Enum):
    UNASSIGNED_START_PASSED = "UNASSIGNED_START_PASSED"
    UNASSIGNED_NEAR_START = "UNASSIGNED_NEAR_START"
    NO_LIVE_OFFERS = "NO_LIVE_OFFERS"
    ASSIGNED_START_PASSED = "ASSIGNED_START_PASSED"
    VISIT_OVERRUN = "VISIT_OVERRUN"
    APPROVAL_STALLED = "APPROVAL_STALLED"
    WORK_REQUEST_REVIEW_OVERDUE = "WORK_REQUEST_REVIEW_OVERDUE"
    ASSIGNED_WORKER_UNDISPATCHABLE = "ASSIGNED_WORKER_UNDISPATCHABLE"


@dataclass(frozen=True)
class RiskPolicy:
    unassigned_lead_time: timedelta = timedelta(hours=4)
    approval_stall_after: timedelta = timedelta(hours=2)
    work_request_review_after: timedelta = timedelta(minutes=30)


DEFAULT_RISK_POLICY = RiskPolicy()


@dataclass(frozen=True)
class JobRiskSnapshot:
    status: JobStatus
    scheduled_start: datetime
    scheduled_end: datetime
    last_changed_at: datetime
    live_offer_count: int
    oldest_unreviewed_work_request_at: datetime | None
    has_worker: bool
    worker_dispatchable: bool


@dataclass(frozen=True)
class JobRisk:
    code: RiskCode
    severity: RiskSeverity
    detail: str


def evaluate_job_risks(
    snapshot: JobRiskSnapshot,
    now: datetime,
    policy: RiskPolicy = DEFAULT_RISK_POLICY,
) -> list[JobRisk]:
    """Return every policy finding for one job, most severe first."""
    risks: list[JobRisk] = []
    status = snapshot.status

    if status in UNASSIGNED_JOB_STATUSES:
        if snapshot.scheduled_start <= now:
            risks.append(
                JobRisk(
                    RiskCode.UNASSIGNED_START_PASSED,
                    RiskSeverity.CRITICAL,
                    "Scheduled start has passed and no worker is assigned.",
                )
            )
        elif snapshot.scheduled_start - now <= policy.unassigned_lead_time:
            risks.append(
                JobRisk(
                    RiskCode.UNASSIGNED_NEAR_START,
                    RiskSeverity.HIGH,
                    "Scheduled start is inside the unassigned lead-time window.",
                )
            )
        if status != JobStatus.CREATED and snapshot.live_offer_count == 0:
            risks.append(
                JobRisk(
                    RiskCode.NO_LIVE_OFFERS,
                    RiskSeverity.HIGH,
                    "Matching has no pending, unexpired offers; rematch or assign manually.",
                )
            )

    if status == JobStatus.ASSIGNED and snapshot.scheduled_start <= now:
        risks.append(
            JobRisk(
                RiskCode.ASSIGNED_START_PASSED,
                RiskSeverity.HIGH,
                "Scheduled start has passed and the technician is not en route.",
            )
        )

    if status in FIELD_EXECUTION_STATUSES and snapshot.scheduled_end <= now:
        risks.append(
            JobRisk(
                RiskCode.VISIT_OVERRUN,
                RiskSeverity.MEDIUM,
                "Visit is still open after its scheduled end.",
            )
        )

    if (
        status == JobStatus.AWAITING_APPROVAL
        and now - snapshot.last_changed_at >= policy.approval_stall_after
    ):
        risks.append(
            JobRisk(
                RiskCode.APPROVAL_STALLED,
                RiskSeverity.MEDIUM,
                "Job has been awaiting additional-work approval beyond the policy window.",
            )
        )

    if (
        snapshot.oldest_unreviewed_work_request_at is not None
        and now - snapshot.oldest_unreviewed_work_request_at >= policy.work_request_review_after
    ):
        risks.append(
            JobRisk(
                RiskCode.WORK_REQUEST_REVIEW_OVERDUE,
                RiskSeverity.HIGH,
                "A submitted work request is waiting for operations review.",
            )
        )

    if (
        status in ASSIGNED_WORK_STATUSES
        and snapshot.has_worker
        and not snapshot.worker_dispatchable
    ):
        risks.append(
            JobRisk(
                RiskCode.ASSIGNED_WORKER_UNDISPATCHABLE,
                RiskSeverity.HIGH,
                "Assigned worker or vendor is no longer active and available.",
            )
        )

    return sorted(risks, key=lambda risk: SEVERITY_RANK[risk.severity])


def highest_severity(risks: list[JobRisk]) -> RiskSeverity | None:
    return min(
        (risk.severity for risk in risks),
        key=SEVERITY_RANK.__getitem__,
        default=None,
    )
