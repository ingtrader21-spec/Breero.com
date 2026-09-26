import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.domains.dispatch.control_center import OperationsControlCenterService, QueueFilters
from app.domains.dispatch.risk import RiskCode, RiskSeverity
from app.domains.jobs.models import Job, JobStatus
from app.domains.workforce.models import VendorStatus, WorkerStatus

NOW = datetime(2026, 9, 25, 12, tzinfo=UTC)


def row(job: Job, **overrides) -> SimpleNamespace:
    values = dict(
        Job=job,
        service_name="Water heater repair",
        vendor_name=None,
        vendor_status=None,
        worker_first_name=None,
        worker_last_name=None,
        worker_status=None,
        worker_available=None,
        city="Austin",
        state_code="TX",
        postal_code="78701",
        country_code="US",
        timezone_name="America/Chicago",
        service_area_id=None,
        service_area_name=None,
        live_offers=0,
        unreviewed=0,
        oldest_unreviewed=None,
        last_event_at=None,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def make_job(**overrides) -> Job:
    values = dict(
        id=uuid.uuid4(),
        booking_id=uuid.uuid4(),
        service_id=uuid.uuid4(),
        address_id=uuid.uuid4(),
        status=JobStatus.CREATED,
        scheduled_start=NOW + timedelta(hours=2),
        scheduled_end=NOW + timedelta(hours=4),
        version=1,
        created_at=NOW - timedelta(hours=1),
        updated_at=NOW - timedelta(minutes=5),
    )
    values.update(overrides)
    return Job(**values)


def service() -> OperationsControlCenterService:
    return OperationsControlCenterService(MagicMock(), now=NOW)


def test_unassigned_row_projects_area_location_and_server_risk() -> None:
    job = make_job()
    item = service()._item(row(job))

    assert item.job_id == job.id and item.status == JobStatus.CREATED
    assert item.location.city == "Austin" and item.location.postal_code == "78701"
    assert item.vendor is None and item.worker is None
    assert [risk.code for risk in item.risks] == [RiskCode.UNASSIGNED_NEAR_START]
    assert item.highest_severity == RiskSeverity.HIGH
    assert item.last_changed_at == NOW - timedelta(minutes=5)


def test_assigned_row_reports_undispatchable_worker() -> None:
    vendor_id, worker_id = uuid.uuid4(), uuid.uuid4()
    job = make_job(
        status=JobStatus.ASSIGNED,
        vendor_id=vendor_id,
        worker_id=worker_id,
        scheduled_start=NOW + timedelta(days=1),
        scheduled_end=NOW + timedelta(days=1, hours=2),
    )
    item = service()._item(
        row(
            job,
            vendor_name="Acme Plumbing",
            vendor_status=VendorStatus.ACTIVE,
            worker_first_name="Ana",
            worker_last_name="Diaz",
            worker_status=WorkerStatus.ACTIVE,
            worker_available=False,
        )
    )

    assert item.vendor is not None and item.vendor.name == "Acme Plumbing"
    assert item.worker is not None and item.worker.name == "Ana Diaz"
    assert item.worker.available is False
    assert [risk.code for risk in item.risks] == [RiskCode.ASSIGNED_WORKER_UNDISPATCHABLE]


def test_naive_database_timestamps_are_treated_as_utc() -> None:
    job = make_job(
        scheduled_start=(NOW - timedelta(minutes=1)).replace(tzinfo=None),
        scheduled_end=(NOW + timedelta(hours=1)).replace(tzinfo=None),
    )
    item = service()._item(
        row(job, last_event_at=(NOW - timedelta(minutes=2)).replace(tzinfo=None))
    )
    assert item.scheduled_start.tzinfo is not None
    assert item.last_changed_at == NOW - timedelta(minutes=2)
    assert item.highest_severity == RiskSeverity.CRITICAL


def test_unreviewed_work_request_count_and_age_flow_into_risk() -> None:
    job = make_job(
        status=JobStatus.AWAITING_APPROVAL,
        vendor_id=uuid.uuid4(),
        worker_id=uuid.uuid4(),
        scheduled_start=NOW - timedelta(hours=1),
        scheduled_end=NOW + timedelta(hours=1),
    )
    item = service()._item(
        row(
            job,
            vendor_name="Acme",
            vendor_status=VendorStatus.ACTIVE,
            worker_first_name="Ana",
            worker_last_name="Diaz",
            worker_status=WorkerStatus.ACTIVE,
            worker_available=True,
            unreviewed=2,
            oldest_unreviewed=NOW - timedelta(hours=1),
            last_event_at=NOW - timedelta(minutes=10),
        )
    )
    assert item.unreviewed_work_request_count == 2
    assert {risk.code for risk in item.risks} == {RiskCode.WORK_REQUEST_REVIEW_OVERDUE}


def test_default_queue_conditions_exclude_terminal_jobs() -> None:
    [condition] = OperationsControlCenterService._conditions(QueueFilters())
    compiled = str(condition.compile(compile_kwargs={"literal_binds": True}))
    assert "COMPLETED" not in compiled and "CANCELLED" not in compiled
    assert "CREATED" in compiled


def test_explicit_statuses_and_filters_add_conditions() -> None:
    conditions = OperationsControlCenterService._conditions(
        QueueFilters(
            statuses=(JobStatus.COMPLETED,),
            vendor_id=uuid.uuid4(),
            service_area_id=uuid.uuid4(),
            unassigned_only=True,
            scheduled_from=NOW,
            scheduled_to=NOW + timedelta(days=1),
        )
    )
    status_condition = str(conditions[0].compile(compile_kwargs={"literal_binds": True}))
    assert "COMPLETED" in status_condition and "CREATED" not in status_condition
    compiled = " ".join(str(condition.compile()) for condition in conditions[1:])
    assert "service_area_id" in compiled and "vendor_id" in compiled
    assert "scheduled_start" in compiled
    assert len(conditions) == 6
