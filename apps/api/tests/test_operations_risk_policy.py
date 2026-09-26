from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.domains.dispatch.risk import (
    DEFAULT_RISK_POLICY,
    JobRiskSnapshot,
    RiskCode,
    RiskPolicy,
    RiskSeverity,
    evaluate_job_risks,
    highest_severity,
)
from app.domains.jobs.lifecycle import (
    ACTIVE_JOB_STATUSES,
    DISPATCH_OWNED_TARGETS,
    TECHNICIAN_COMMANDS,
    TERMINAL_JOB_STATUSES,
    UNASSIGNED_JOB_STATUSES,
    allowed_transitions,
    operator_transitions,
    technician_commands,
)
from app.domains.jobs.models import JobStatus
from app.domains.jobs.service import TRANSITIONS

NOW = datetime(2026, 9, 25, 15, 0, tzinfo=UTC)


def snapshot(**overrides) -> JobRiskSnapshot:
    base = JobRiskSnapshot(
        status=JobStatus.ASSIGNED,
        scheduled_start=NOW + timedelta(days=1),
        scheduled_end=NOW + timedelta(days=1, hours=2),
        last_changed_at=NOW,
        live_offer_count=0,
        oldest_unreviewed_work_request_at=None,
        has_worker=True,
        worker_dispatchable=True,
    )
    return replace(base, **overrides)


def codes(value: JobRiskSnapshot, policy: RiskPolicy = DEFAULT_RISK_POLICY) -> set[RiskCode]:
    return {risk.code for risk in evaluate_job_risks(value, NOW, policy)}


def test_healthy_future_assigned_job_has_no_risk() -> None:
    assert evaluate_job_risks(snapshot(), NOW) == []


def test_unassigned_job_past_start_is_critical() -> None:
    risks = evaluate_job_risks(
        snapshot(
            status=JobStatus.CREATED,
            scheduled_start=NOW - timedelta(minutes=1),
            has_worker=False,
        ),
        NOW,
    )
    assert [risk.code for risk in risks] == [RiskCode.UNASSIGNED_START_PASSED]
    assert risks[0].severity == RiskSeverity.CRITICAL


@pytest.mark.parametrize(
    ("lead", "flagged"),
    [(timedelta(hours=4), True), (timedelta(hours=3), True), (timedelta(hours=4, minutes=1), False)],
)
def test_unassigned_lead_time_window_uses_server_policy(lead: timedelta, flagged: bool) -> None:
    value = snapshot(status=JobStatus.CREATED, scheduled_start=NOW + lead, has_worker=False)
    assert (RiskCode.UNASSIGNED_NEAR_START in codes(value)) is flagged


def test_lead_time_threshold_is_configurable() -> None:
    value = snapshot(
        status=JobStatus.CREATED,
        scheduled_start=NOW + timedelta(hours=6),
        has_worker=False,
    )
    assert RiskCode.UNASSIGNED_NEAR_START not in codes(value)
    wider = RiskPolicy(unassigned_lead_time=timedelta(hours=8))
    assert RiskCode.UNASSIGNED_NEAR_START in codes(value, wider)


@pytest.mark.parametrize("status", [JobStatus.MATCHING, JobStatus.OFFERED])
def test_matching_without_live_offers_needs_rematch(status: JobStatus) -> None:
    value = snapshot(status=status, has_worker=False, live_offer_count=0)
    assert RiskCode.NO_LIVE_OFFERS in codes(value)
    assert RiskCode.NO_LIVE_OFFERS not in codes(replace(value, live_offer_count=2))


def test_created_job_is_not_flagged_for_missing_offers_before_matching() -> None:
    value = snapshot(status=JobStatus.CREATED, has_worker=False, live_offer_count=0)
    assert RiskCode.NO_LIVE_OFFERS not in codes(value)


def test_assigned_job_past_start_is_flagged() -> None:
    value = snapshot(scheduled_start=NOW - timedelta(minutes=5))
    assert codes(value) == {RiskCode.ASSIGNED_START_PASSED}


@pytest.mark.parametrize(
    "status",
    [JobStatus.EN_ROUTE, JobStatus.ON_SITE, JobStatus.DIAGNOSING, JobStatus.IN_PROGRESS],
)
def test_field_execution_past_scheduled_end_overruns(status: JobStatus) -> None:
    value = snapshot(
        status=status,
        scheduled_start=NOW - timedelta(hours=3),
        scheduled_end=NOW - timedelta(minutes=1),
    )
    assert codes(value) == {RiskCode.VISIT_OVERRUN}


def test_awaiting_approval_stalls_after_policy_window() -> None:
    fresh = snapshot(status=JobStatus.AWAITING_APPROVAL, last_changed_at=NOW - timedelta(minutes=30))
    stale = replace(fresh, last_changed_at=NOW - timedelta(hours=2))
    assert RiskCode.APPROVAL_STALLED not in codes(fresh)
    assert RiskCode.APPROVAL_STALLED in codes(stale)


def test_unreviewed_work_request_becomes_overdue() -> None:
    recent = snapshot(
        status=JobStatus.AWAITING_APPROVAL,
        oldest_unreviewed_work_request_at=NOW - timedelta(minutes=10),
    )
    overdue = replace(recent, oldest_unreviewed_work_request_at=NOW - timedelta(minutes=31))
    assert RiskCode.WORK_REQUEST_REVIEW_OVERDUE not in codes(recent)
    assert RiskCode.WORK_REQUEST_REVIEW_OVERDUE in codes(overdue)


def test_undispatchable_assigned_worker_is_flagged() -> None:
    value = snapshot(worker_dispatchable=False)
    assert codes(value) == {RiskCode.ASSIGNED_WORKER_UNDISPATCHABLE}


@pytest.mark.parametrize("status", sorted(TERMINAL_JOB_STATUSES, key=lambda s: s.value))
def test_terminal_jobs_never_raise_risk(status: JobStatus) -> None:
    value = snapshot(
        status=status,
        scheduled_start=NOW - timedelta(days=2),
        scheduled_end=NOW - timedelta(days=2),
        worker_dispatchable=False,
        last_changed_at=NOW - timedelta(days=2),
    )
    assert evaluate_job_risks(value, NOW) == []


def test_risks_are_ordered_most_severe_first() -> None:
    risks = evaluate_job_risks(
        snapshot(
            status=JobStatus.OFFERED,
            scheduled_start=NOW - timedelta(minutes=10),
            has_worker=False,
            live_offer_count=0,
        ),
        NOW,
    )
    assert [risk.severity for risk in risks] == [RiskSeverity.CRITICAL, RiskSeverity.HIGH]
    assert highest_severity(risks) == RiskSeverity.CRITICAL
    assert highest_severity([]) is None


def test_lifecycle_sets_partition_job_statuses() -> None:
    assert ACTIVE_JOB_STATUSES | TERMINAL_JOB_STATUSES == set(JobStatus)
    assert not ACTIVE_JOB_STATUSES & TERMINAL_JOB_STATUSES
    assert UNASSIGNED_JOB_STATUSES <= ACTIVE_JOB_STATUSES


@pytest.mark.parametrize("status", list(JobStatus))
def test_allowed_transitions_mirror_the_authoritative_state_machine(status: JobStatus) -> None:
    targets = allowed_transitions(status)
    assert set(targets) == TRANSITIONS[status]
    order = list(JobStatus)
    assert targets == sorted(targets, key=order.index)


@pytest.mark.parametrize("status", list(JobStatus))
def test_operator_transitions_exclude_dispatch_owned_targets(status: JobStatus) -> None:
    targets = operator_transitions(status)
    assert set(targets) == TRANSITIONS[status] - DISPATCH_OWNED_TARGETS
    assert targets == [target for target in allowed_transitions(status) if target in targets]


def test_unassigned_jobs_can_only_be_cancelled_by_generic_transition() -> None:
    for status in UNASSIGNED_JOB_STATUSES:
        assert operator_transitions(status) == [JobStatus.CANCELLED]
    assert operator_transitions(JobStatus.ASSIGNED) == [JobStatus.EN_ROUTE, JobStatus.CANCELLED]


def test_technician_commands_only_offer_legal_next_steps() -> None:
    assert technician_commands(JobStatus.ASSIGNED) == ["en-route"]
    assert technician_commands(JobStatus.EN_ROUTE) == ["arrive"]
    assert technician_commands(JobStatus.ON_SITE) == ["diagnose", "start"]
    assert technician_commands(JobStatus.COMPLETED) == []
    for status in JobStatus:
        for command in technician_commands(status):
            assert TECHNICIAN_COMMANDS[command] in TRANSITIONS[status]
