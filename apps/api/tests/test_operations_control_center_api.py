import uuid
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import operations
from app.api.v1.jobs import transitions as job_transitions
from app.api.v1.operations import control_center
from app.api.v1.operations import dispatch as dispatch_routes
from app.db.session import get_db
from app.domains.auth import dependencies as auth_dependencies
from app.domains.auth.dependencies import current_user
from app.domains.auth.models import AccessRole, User, UserRole
from app.domains.dispatch.control_center import QueueFilters
from app.domains.dispatch.models import Assignment, AssignmentStatus
from app.domains.dispatch.operations_schemas import (
    CapacityBoard,
    CapacityTotals,
    ExceptionQueue,
    IntegrationFailurePage,
    IntegrationHealthSummary,
    JobLocationSummary,
    OperationsDashboard,
    QueueItem,
    QueuePage,
    RiskPolicyRead,
    ServiceAreaProjection,
    WorkforceSummary,
)
from app.domains.jobs.models import Job, JobStatus
from app.main import app

NOW = datetime(2026, 9, 25, 12, tzinfo=UTC)
BASE = "/api/v1/operations/control-center"
READ_PATHS = [
    f"{BASE}/summary",
    f"{BASE}/queue",
    f"{BASE}/exceptions",
    f"{BASE}/capacity",
    f"{BASE}/service-areas",
    f"{BASE}/integration-failures",
    f"{BASE}/jobs/{uuid.uuid4()}",
    f"{BASE}/jobs/{uuid.uuid4()}/candidates",
]
ROLE_GRANTS = {
    UserRole.customer: [AccessRole.customer],
    UserRole.technician: [AccessRole.technician],
    UserRole.vendor_admin: [AccessRole.vendor_admin],
    UserRole.finance: [AccessRole.finance],
    UserRole.operations: [AccessRole.operations, AccessRole.ops_manager],
    UserRole.admin: [AccessRole.admin, AccessRole.superadmin],
}


def make_user(role: UserRole) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4().hex}@example.com",
        password_hash="disabled",
        full_name="Ops Tester",
        role=role,
        is_active=True,
        email_verified=True,
        credential_version=1,
    )


def queue_item() -> QueueItem:
    return QueueItem(
        job_id=uuid.uuid4(),
        booking_id=uuid.uuid4(),
        status=JobStatus.CREATED,
        version=1,
        scheduled_start=NOW + timedelta(hours=1),
        scheduled_end=NOW + timedelta(hours=3),
        service_id=uuid.uuid4(),
        service_name="Repair",
        location=JobLocationSummary(
            city="Austin",
            state_code="TX",
            postal_code="78701",
            country_code="US",
            timezone_name="America/Chicago",
            service_area_id=None,
            service_area_name=None,
        ),
        vendor=None,
        worker=None,
        live_offer_count=0,
        unreviewed_work_request_count=0,
        last_changed_at=NOW,
        risks=[],
        highest_severity=None,
    )


class FakeControlCenter:
    instances: list["FakeControlCenter"] = []

    def __init__(self, session) -> None:
        self.session = session
        self.calls: list[tuple[str, tuple, dict]] = []
        FakeControlCenter.instances.append(self)

    async def queue(self, filters, *, limit, offset):
        self.calls.append(("queue", (filters,), {"limit": limit, "offset": offset}))
        return QueuePage(
            generated_at=NOW, items=[queue_item()], total=1, limit=limit, offset=offset,
            scan_truncated=False,
        )

    async def exceptions(self, severity=None):
        self.calls.append(("exceptions", (severity,), {}))
        return ExceptionQueue(
            generated_at=NOW,
            policy=RiskPolicyRead(
                unassigned_lead_time_minutes=240,
                approval_stall_after_minutes=120,
                work_request_review_after_minutes=30,
            ),
            items=[],
            by_severity=[],
            by_code=[],
            scanned_jobs=0,
            scan_truncated=False,
        )

    async def dashboard(self):
        return OperationsDashboard(
            generated_at=NOW,
            jobs_by_status=[],
            active_jobs=0,
            unassigned_jobs=0,
            scheduled_next_24h=0,
            live_offers=0,
            work_requests_awaiting_review=0,
            work_requests_awaiting_customer=0,
            risk_by_severity=[],
            at_risk_jobs=0,
            risk_scan_truncated=False,
            workforce=WorkforceSummary(active_vendors=0, active_workers=0, dispatchable_workers=0),
            integrations=IntegrationHealthSummary(failed=0, retrying=0),
        )

    async def capacity(self, day, *, vendor_id=None, include_inactive=False):
        self.calls.append(("capacity", (day,), {"vendor_id": vendor_id}))
        start = datetime.combine(day, datetime.min.time(), tzinfo=UTC)
        return CapacityBoard(
            generated_at=NOW,
            date=day,
            weekday=day.weekday(),
            window_start=start,
            window_end=start + timedelta(days=1),
            workers=[],
            totals=CapacityTotals(
                workers=0, daily_capacity=0, jobs_in_window=0,
                workers_without_hours=0, workers_over_capacity=0,
            ),
            truncated=False,
        )

    async def service_areas(self):
        return ServiceAreaProjection(
            generated_at=NOW, areas=[], unzoned_active_jobs=0, privacy="aggregate only"
        )

    async def integration_failures(self, *, limit, retry_permitted):
        self.calls.append(("integration_failures", (), {"retry_permitted": retry_permitted}))
        return IntegrationFailurePage(generated_at=NOW, items=[], retry_permitted=retry_permitted)


@pytest.fixture
def client_for(monkeypatch):
    FakeControlCenter.instances.clear()
    monkeypatch.setattr(control_center, "OperationsControlCenterService", FakeControlCenter)

    def build(role: UserRole) -> TestClient:
        user = make_user(role)
        grants = ROLE_GRANTS[role]

        class FakeAccessService:
            def __init__(self, _session) -> None:
                pass

            async def context(self, _user, _brand_key=None):
                return SimpleNamespace(roles=grants, permissions=[])

        async def fake_effective_roles(_session, _user):
            return set(grants)

        async def override_user() -> User:
            return user

        async def override_db():
            yield MagicMock()

        monkeypatch.setattr(auth_dependencies, "AccessService", FakeAccessService)
        monkeypatch.setattr(control_center, "effective_roles", fake_effective_roles)
        app.dependency_overrides[current_user] = override_user
        app.dependency_overrides[get_db] = override_db
        return TestClient(app)

    yield build
    app.dependency_overrides.clear()


def test_control_center_routes_are_registered_with_unique_operation_ids() -> None:
    paths = app.openapi()["paths"]
    expected = {
        f"{BASE}/summary": "get",
        f"{BASE}/queue": "get",
        f"{BASE}/exceptions": "get",
        f"{BASE}/capacity": "get",
        f"{BASE}/service-areas": "get",
        f"{BASE}/integration-failures": "get",
        f"{BASE}/jobs/{{job_id}}": "get",
        f"{BASE}/jobs/{{job_id}}/candidates": "get",
        "/api/v1/operations/jobs/{job_id}/reassign": "post",
    }
    for path, method in expected.items():
        assert method in paths[path], path
        assert paths[path][method]["security"] == [{"HTTPBearer": []}]
    operation_ids = [
        operation["operationId"]
        for methods in paths.values()
        for operation in methods.values()
        if isinstance(operation, dict) and "operationId" in operation
    ]
    assert len(operation_ids) == len(set(operation_ids))


def test_operations_package_exports_control_center_handlers() -> None:
    assert operations.operations_dashboard is control_center.operations_dashboard
    assert operations.dispatch_queue is control_center.dispatch_queue
    assert operations.reassign_job is dispatch_routes.reassign_job


def test_projection_contracts_expose_no_street_coordinates_or_contact_fields() -> None:
    schemas = app.openapi()["components"]["schemas"]
    forbidden = {"line1", "line2", "formatted_address", "location_point", "email", "phone",
                 "payload", "last_error", "boundary", "center", "latitude", "longitude"}
    for name in (
        "QueueItem",
        "JobLocationSummary",
        "ServiceAreaOperations",
        "IntegrationEventSummary",
        "WorkerCapacity",
        "AssignmentCandidate",
        "PartySummary",
    ):
        properties = set(schemas[name]["properties"])
        assert not properties & forbidden, (name, properties & forbidden)


def test_unauthenticated_requests_are_rejected() -> None:
    async def override_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        for path in READ_PATHS:
            assert client.get(path).status_code == 401, path
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "role", [UserRole.customer, UserRole.technician, UserRole.vendor_admin, UserRole.finance]
)
def test_non_operations_roles_are_forbidden(client_for, role: UserRole) -> None:
    client = client_for(role)
    for path in READ_PATHS:
        assert client.get(path).status_code == 403, (role, path)
    reassign = client.post(
        f"/api/v1/operations/jobs/{uuid.uuid4()}/reassign",
        json={"vendor_id": str(uuid.uuid4()), "worker_id": str(uuid.uuid4()), "reason": "x"},
    )
    assert reassign.status_code == 403
    assert FakeControlCenter.instances == []


@pytest.mark.parametrize("role", [UserRole.operations, UserRole.admin])
def test_operations_roles_read_every_projection(client_for, role: UserRole) -> None:
    client = client_for(role)
    for path in (
        f"{BASE}/summary",
        f"{BASE}/queue",
        f"{BASE}/exceptions",
        f"{BASE}/capacity",
        f"{BASE}/service-areas",
        f"{BASE}/integration-failures",
    ):
        response = client.get(path)
        assert response.status_code == 200, (path, response.text)


def test_queue_filters_are_parsed_into_domain_filters(client_for) -> None:
    client = client_for(UserRole.operations)
    vendor_id = uuid.uuid4()
    response = client.get(
        f"{BASE}/queue",
        params=[
            ("status", "CREATED"),
            ("status", "OFFERED"),
            ("vendor_id", str(vendor_id)),
            ("unassigned_only", "true"),
            ("severity", "HIGH"),
            ("limit", "25"),
            ("offset", "50"),
        ],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1 and body["limit"] == 25 and body["offset"] == 50
    name, (filters,), kwargs = FakeControlCenter.instances[-1].calls[-1]
    assert name == "queue" and kwargs == {"limit": 25, "offset": 50}
    assert isinstance(filters, QueueFilters)
    assert filters.statuses == (JobStatus.CREATED, JobStatus.OFFERED)
    assert filters.vendor_id == vendor_id and filters.unassigned_only is True
    assert filters.severity is not None and filters.severity.value == "HIGH"


@pytest.mark.parametrize(
    "params",
    [
        {"limit": "0"},
        {"limit": "201"},
        {"offset": "-1"},
        {"status": "NOT_A_STATUS"},
        {"severity": "LOW"},
        {"scheduled_from": "2026-09-25T10:00:00Z", "scheduled_to": "2026-09-25T09:00:00Z"},
    ],
)
def test_queue_rejects_invalid_filters(client_for, params) -> None:
    client = client_for(UserRole.operations)
    assert client.get(f"{BASE}/queue", params=params).status_code == 422


def test_capacity_accepts_explicit_date(client_for) -> None:
    client = client_for(UserRole.operations)
    response = client.get(f"{BASE}/capacity", params={"date": "2026-10-01"})
    assert response.status_code == 200
    assert response.json()["weekday"] == date(2026, 10, 1).weekday()
    assert FakeControlCenter.instances[-1].calls[-1][1] == (date(2026, 10, 1),)


@pytest.mark.parametrize(
    ("role", "permitted"), [(UserRole.operations, False), (UserRole.admin, True)]
)
def test_integration_failure_retry_is_only_advertised_to_retry_roles(
    client_for, role: UserRole, permitted: bool
) -> None:
    client = client_for(role)
    response = client.get(f"{BASE}/integration-failures")
    assert response.status_code == 200
    assert response.json()["retry_permitted"] is permitted


def test_reassign_route_returns_readback(client_for, monkeypatch) -> None:
    client = client_for(UserRole.operations)
    job = Job(
        id=uuid.uuid4(),
        booking_id=uuid.uuid4(),
        service_id=uuid.uuid4(),
        address_id=uuid.uuid4(),
        status=JobStatus.ASSIGNED,
        scheduled_start=NOW,
        scheduled_end=NOW + timedelta(hours=2),
        version=5,
    )
    replacement = Assignment(
        id=uuid.uuid4(),
        job_id=job.id,
        vendor_id=uuid.uuid4(),
        worker_id=uuid.uuid4(),
        status=AssignmentStatus.ACTIVE,
        assigned_at=NOW,
    )
    released = Assignment(id=uuid.uuid4(), status=AssignmentStatus.RELEASED)
    received: dict = {}

    class FakeDispatchService:
        def __init__(self, _session) -> None:
            pass

        async def reassign(self, *args):
            received["args"] = args
            return replacement, released, job

    monkeypatch.setattr(dispatch_routes, "DispatchService", FakeDispatchService)
    response = client.post(
        f"/api/v1/operations/jobs/{job.id}/reassign",
        json={
            "vendor_id": str(replacement.vendor_id),
            "worker_id": str(replacement.worker_id),
            "reason": "Closer technician available",
            "expected_version": 4,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["assignment"]["id"] == str(replacement.id)
    assert body["released_assignment_id"] == str(released.id)
    assert body["job_version"] == 5 and body["job_status"] == "ASSIGNED"
    assert received["args"][0] == job.id
    assert received["args"][4:] == ("Closer technician available", 4)


@pytest.mark.parametrize("target", ["MATCHING", "OFFERED", "ASSIGNED"])
def test_generic_transition_refuses_dispatch_owned_targets(client_for, monkeypatch, target) -> None:
    client = client_for(UserRole.operations)

    class ExplodingJobService:
        def __init__(self, _session) -> None:
            raise AssertionError("dispatch-owned targets must not reach the job service")

    monkeypatch.setattr(job_transitions, "JobService", ExplodingJobService)
    response = client.post(
        f"/api/v1/jobs/{uuid.uuid4()}/transition", json={"status": target, "reason": "manual"}
    )
    assert response.status_code == 409
    assert "match/assign" in response.json()["detail"]


@pytest.mark.parametrize(
    "payload",
    [
        {"vendor_id": str(uuid.uuid4()), "worker_id": str(uuid.uuid4()), "reason": ""},
        {"vendor_id": str(uuid.uuid4()), "worker_id": str(uuid.uuid4())},
        {
            "vendor_id": str(uuid.uuid4()),
            "worker_id": str(uuid.uuid4()),
            "reason": "ok",
            "expected_version": 0,
        },
    ],
)
def test_reassign_requires_reason_and_positive_version(client_for, payload) -> None:
    client = client_for(UserRole.operations)
    response = client.post(f"/api/v1/operations/jobs/{uuid.uuid4()}/reassign", json=payload)
    assert response.status_code == 422
