import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.errors import DomainError
from app.db.session import get_db
from app.domains.auth.access_service import DEFAULT_ACCESS, DEFAULT_PERMISSIONS, AccessService
from app.domains.auth.dependencies import current_user
from app.domains.auth.models import User, UserRole
from app.domains.auth.schemas import PortalContext, UserRead
from app.domains.finance.models import EarningStatus, PayoutBatch, PayoutStatus, VendorEarning
from app.domains.finance.read_models import (
    EarningPage,
    FinanceCapabilityState,
    FinanceExceptionKind,
    PayoutAction,
)
from app.domains.finance.read_service import (
    FinanceReadService,
    ProviderFinanceService,
    allowed_payout_actions,
    finance_status,
    payout_history,
)
from app.domains.finance.service import FinanceService
from app.integrations.payouts import FakePayoutGateway
from app.main import app

NOW = datetime(2026, 9, 1, tzinfo=UTC)


def make_user(role: UserRole) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4().hex}@example.com",
        password_hash="disabled",
        full_name="Finance Test",
        role=role,
        is_active=True,
        email_verified=True,
        credential_version=1,
    )


def make_batch(status: PayoutStatus = PayoutStatus.PENDING_APPROVAL, **kwargs) -> PayoutBatch:
    values = {
        "id": uuid.uuid4(),
        "reference": f"PAY-{uuid.uuid4().hex[:8]}",
        "status": status,
        "currency": "USD",
        "total_minor": 1000,
        "earning_count": 2,
        "created_at": NOW,
    }
    values.update(kwargs)
    return PayoutBatch(**values)


def make_earning(vendor_id: uuid.UUID, status: EarningStatus, **kwargs) -> VendorEarning:
    values = {
        "id": uuid.uuid4(),
        "vendor_id": vendor_id,
        "job_id": uuid.uuid4(),
        "compensation_snapshot_id": uuid.uuid4(),
        "gross_minor": 1000,
        "fee_minor": 200,
        "net_minor": 800,
        "adjustment_total_minor": 0,
        "currency": "USD",
        "status": status,
        "available_at": NOW,
        "created_at": NOW,
    }
    values.update(kwargs)
    return VendorEarning(**values)


class Result:
    def __init__(self, rows=None) -> None:
        self._rows = list(rows or [])

    def all(self):
        return list(self._rows)

    def one(self):
        return self._rows[0]


class FakeSession:
    def __init__(self, *, scalar=None, scalars=None, execute=None) -> None:
        self._scalar = list(scalar or [])
        self._scalars = list(scalars or [])
        self._execute = list(execute or [])
        self.statements: list[object] = []

    async def scalar(self, statement):
        self.statements.append(statement)
        return self._scalar.pop(0) if self._scalar else None

    async def scalars(self, statement):
        self.statements.append(statement)
        return Result(self._scalars.pop(0) if self._scalars else [])

    async def execute(self, statement):
        self.statements.append(statement)
        return Result(self._execute.pop(0) if self._execute else [])


def bound_values(statement) -> list[object]:
    return list(statement.compile(dialect=postgresql.dialect()).params.values())


# ----- contract and disabled-capability behaviour -------------------------


def test_finance_read_routes_are_mounted_while_payout_commands_stay_gated() -> None:
    assert settings.payout_enabled is False
    paths = app.openapi()["paths"]
    reads = {
        "/api/v1/finance/status": {"get"},
        "/api/v1/finance/earnings": {"get"},
        "/api/v1/finance/earnings/summary": {"get"},
        "/api/v1/finance/exceptions": {"get"},
        "/api/v1/finance/payout-candidates": {"get"},
        "/api/v1/finance/payout-batches": {"get"},
        "/api/v1/finance/payout-batches/{batch_id}": {"get"},
        "/api/v1/finance/payout-batches/{batch_id}/history": {"get"},
        "/api/v1/finance/payments": {"get"},
        "/api/v1/finance/refunds": {"get"},
        "/api/v1/provider/finance/summary": {"get"},
        "/api/v1/provider/finance/earnings": {"get"},
        "/api/v1/provider/finance/payouts": {"get"},
        "/api/v1/provider/finance/payouts/{payout_id}": {"get"},
    }
    for path, methods in reads.items():
        assert set(paths[path]) == methods, path
    for command in (
        "/api/v1/finance/payout-batches/{batch_id}/approve",
        "/api/v1/finance/payout-batches/{batch_id}/submit",
        "/api/v1/finance/compensation-plans",
        "/api/v1/finance/earnings/{earning_id}/adjustments",
    ):
        assert command not in paths
    assert "post" not in paths["/api/v1/finance/payout-batches"]
    # No refund or capture command exists on the finance surface.
    assert not [p for p in paths if p.startswith("/api/v1/finance/") and "refund" in p and p != "/api/v1/finance/refunds"]


def test_provider_finance_contract_never_accepts_a_vendor_id() -> None:
    paths = app.openapi()["paths"]
    for path, operations in paths.items():
        if not path.startswith("/api/v1/provider/finance"):
            continue
        for operation in operations.values():
            names = {parameter["name"] for parameter in operation.get("parameters", [])}
            assert "vendor_id" not in names, path


def test_finance_status_reports_disabled_and_not_implemented_capabilities(monkeypatch) -> None:
    monkeypatch.setattr(settings, "payout_enabled", False)
    status = finance_status()
    assert status.payouts_enabled is False
    assert status.capabilities["payout_commands"] == FinanceCapabilityState.DISABLED
    assert status.capabilities["payout_transfer"] == FinanceCapabilityState.NOT_IMPLEMENTED
    assert status.capabilities["refund_commands"] == FinanceCapabilityState.NOT_IMPLEMENTED
    assert status.capabilities["payment_commands"] == FinanceCapabilityState.NOT_IMPLEMENTED
    assert status.capabilities["payout_batches_read"] == FinanceCapabilityState.ENABLED
    monkeypatch.setattr(settings, "payout_enabled", True)
    status = finance_status()
    assert status.capabilities["payout_commands"] == FinanceCapabilityState.ENABLED
    # Enabling payouts never implies a live transfer adapter.
    assert status.capabilities["payout_transfer"] == FinanceCapabilityState.NOT_IMPLEMENTED


def test_no_payout_actions_are_offered_while_disabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "payout_enabled", False)
    for status in PayoutStatus:
        assert allowed_payout_actions(make_batch(status)) == []


def test_payout_action_matrix_enforces_four_eyes(monkeypatch) -> None:
    monkeypatch.setattr(settings, "payout_enabled", True)
    reviewer, approver = uuid.uuid4(), uuid.uuid4()
    pending = make_batch(PayoutStatus.PENDING_APPROVAL, reviewed_by=reviewer)
    assert allowed_payout_actions(pending, reviewer) == []
    assert allowed_payout_actions(pending, approver) == [PayoutAction.approve]
    assert allowed_payout_actions(make_batch(PayoutStatus.APPROVED)) == [PayoutAction.submit]
    submitted = make_batch(PayoutStatus.APPROVED, provider_transfer_id="t-1")
    assert allowed_payout_actions(submitted) == []
    for status in (PayoutStatus.PROCESSING, PayoutStatus.PAID, PayoutStatus.FAILED,
                   PayoutStatus.CANCELLED, PayoutStatus.DRAFT):
        assert allowed_payout_actions(make_batch(status)) == []


async def test_approver_must_differ_from_reviewer(monkeypatch) -> None:
    monkeypatch.setattr(settings, "payout_enabled", True)
    reviewer = uuid.uuid4()
    batch = make_batch(PayoutStatus.PENDING_APPROVAL, reviewed_by=reviewer)
    session = Mock(spec=AsyncSession)
    service = FinanceService(session, FakePayoutGateway())
    service.repo.get_batch = AsyncMock(return_value=batch)  # type: ignore[method-assign]
    with pytest.raises(HTTPException) as error:
        await service.approve_batch(batch.id, reviewer)
    assert (error.value.status_code, error.value.detail) == (
        409,
        "Approver must differ from batch reviewer",
    )
    assert batch.status == PayoutStatus.PENDING_APPROVAL
    session.commit.assert_not_called()

    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    approved = await service.approve_batch(batch.id, uuid.uuid4())
    assert approved.status == PayoutStatus.APPROVED
    session.commit.assert_awaited_once()


def test_payout_history_reads_back_lifecycle_states() -> None:
    reviewer, approver = uuid.uuid4(), uuid.uuid4()
    batch = make_batch(
        PayoutStatus.PROCESSING,
        reviewed_by=reviewer,
        reviewed_at=NOW,
        approved_by=approver,
        approved_at=NOW + timedelta(hours=1),
        submitted_at=NOW + timedelta(hours=2),
        provider_status="processing",
    )
    history = payout_history(batch)
    assert [entry.state for entry in history] == ["CREATED", "APPROVED", "SUBMITTED", "CURRENT"]
    assert history[0].actor_id == reviewer
    assert history[1].actor_id == approver
    assert history[-1].status == PayoutStatus.PROCESSING

    blocked = make_batch(PayoutStatus.APPROVED, approved_at=NOW,
                         failure_reason="integration_not_configured")
    assert [entry.state for entry in payout_history(blocked)] == [
        "CREATED", "APPROVED", "SUBMISSION_BLOCKED", "CURRENT"
    ]


# ----- admin read models --------------------------------------------------


async def test_missing_payout_batch_is_404() -> None:
    service = FinanceReadService(FakeSession())  # type: ignore[arg-type]
    with pytest.raises(DomainError) as error:
        await service.payout_batch(uuid.uuid4())
    assert (error.value.code, error.value.status_code) == ("PAYOUT_BATCH_NOT_FOUND", 404)


async def test_payout_batch_detail_groups_vendor_totals(monkeypatch) -> None:
    monkeypatch.setattr(settings, "payout_enabled", False)
    vendor_a, vendor_b = uuid.uuid4(), uuid.uuid4()
    batch = make_batch()
    earnings = [
        make_earning(vendor_a, EarningStatus.BATCHED, payout_batch_id=batch.id),
        make_earning(vendor_a, EarningStatus.BATCHED, payout_batch_id=batch.id,
                     adjustment_total_minor=-100),
        make_earning(vendor_b, EarningStatus.BATCHED, payout_batch_id=batch.id),
    ]
    service = FinanceReadService(FakeSession(scalar=[batch], scalars=[earnings]))  # type: ignore[arg-type]
    detail = await service.payout_batch(batch.id, uuid.uuid4())
    totals = {item.vendor_id: (item.earning_count, item.total_minor) for item in detail.vendor_totals}
    assert totals == {vendor_a: (2, 1500), vendor_b: (1, 800)}
    assert detail.allowed_actions == []
    assert detail.payouts_enabled is False


async def test_pending_payout_totals_bucket_by_status() -> None:
    session = FakeSession(
        execute=[
            [
                ("USD", EarningStatus.PENDING, 2, 500),
                ("USD", EarningStatus.AVAILABLE, 2, 900),
                ("USD", EarningStatus.HELD, 1, 100),
                ("USD", EarningStatus.BATCHED, 1, 700),
                ("USD", EarningStatus.PAID, 1, 50),
                ("USD", EarningStatus.REVERSED, 1, 0),
            ],
            [("USD", 1, 300)],
        ]
    )
    summary = await FinanceReadService(session).earnings_summary()  # type: ignore[arg-type]
    [usd] = summary.pending_payouts
    assert usd.model_dump() == {
        "currency": "USD",
        "eligible_count": 1,
        "eligible_minor": 300,
        "pending_release_minor": 500,
        "held_minor": 100,
        "in_batch_minor": 700,
        "paid_minor": 50,
    }
    assert len(summary.by_status) == 6


async def test_exceptions_classify_held_reversed_failed_blocked_and_stale() -> None:
    vendor = uuid.uuid4()
    earnings = [
        make_earning(vendor, EarningStatus.HELD),
        make_earning(vendor, EarningStatus.REVERSED, adjustment_total_minor=-800),
    ]
    batches = [
        make_batch(PayoutStatus.FAILED, failure_reason="bank_rejected"),
        make_batch(PayoutStatus.APPROVED, failure_reason="integration_not_configured"),
        make_batch(PayoutStatus.PROCESSING, submitted_at=NOW - timedelta(days=30)),
    ]
    session = FakeSession(scalars=[earnings, batches])
    result = await FinanceReadService(session).exceptions()  # type: ignore[arg-type]
    assert [item.kind for item in result.items] == [
        FinanceExceptionKind.EARNING_HELD,
        FinanceExceptionKind.EARNING_REVERSED,
        FinanceExceptionKind.PAYOUT_FAILED,
        FinanceExceptionKind.PAYOUT_SUBMISSION_BLOCKED,
        FinanceExceptionKind.PAYOUT_PROCESSING_STALE,
    ]
    assert result.items[1].amount_minor == 0
    assert result.total == 5


# ----- provider isolation -------------------------------------------------


async def test_provider_without_vendor_is_forbidden() -> None:
    service = ProviderFinanceService(FakeSession(scalar=[None]))  # type: ignore[arg-type]
    with pytest.raises(DomainError) as error:
        await service.earnings(make_user(UserRole.vendor_admin))
    assert (error.value.code, error.value.status_code) == ("PROVIDER_ACCOUNT_REQUIRED", 403)


async def test_provider_earnings_are_scoped_to_owned_vendor() -> None:
    owned = uuid.uuid4()
    user = make_user(UserRole.vendor_admin)
    session = FakeSession(scalar=[owned, 0])
    await ProviderFinanceService(session).earnings(user)  # type: ignore[arg-type]
    vendor_lookup, count, rows = session.statements
    assert user.id in bound_values(vendor_lookup)
    assert owned in bound_values(count)
    assert owned in bound_values(rows)


async def test_provider_payouts_are_scoped_to_owned_vendor() -> None:
    owned = uuid.uuid4()
    session = FakeSession(scalar=[owned, 0])
    page = await ProviderFinanceService(session).payouts(make_user(UserRole.vendor_admin))  # type: ignore[arg-type]
    assert page.total == 0
    _, count, rows = session.statements
    assert owned in bound_values(count)
    assert owned in bound_values(rows)


async def test_provider_cannot_read_another_vendors_payout() -> None:
    owned = uuid.uuid4()
    # The batch exists but holds none of this vendor's earnings.
    session = FakeSession(scalar=[owned, make_batch()], scalars=[[]])
    service = ProviderFinanceService(session)  # type: ignore[arg-type]
    with pytest.raises(DomainError) as error:
        await service.payout(make_user(UserRole.vendor_admin), uuid.uuid4())
    assert (error.value.code, error.value.status_code) == ("PAYOUT_NOT_FOUND", 404)
    # The batch row is never loaded, so nothing about it can leak.
    assert len(session.statements) == 2
    assert owned in bound_values(session.statements[1])


async def test_provider_payout_detail_exposes_only_vendor_share() -> None:
    owned = uuid.uuid4()
    batch = make_batch(PayoutStatus.APPROVED, total_minor=99_999, earning_count=40,
                       failure_reason="integration_not_configured", approved_at=NOW)
    mine = [make_earning(owned, EarningStatus.BATCHED, payout_batch_id=batch.id)]
    session = FakeSession(scalar=[owned, batch], scalars=[mine])
    detail = await ProviderFinanceService(session).payout(  # type: ignore[arg-type]
        make_user(UserRole.vendor_admin), batch.id
    )
    assert detail.vendor_total_minor == 800
    assert detail.vendor_earning_count == 1
    dumped = detail.model_dump()
    for private in ("total_minor", "earning_count", "failure_reason", "reviewed_by",
                    "approved_by", "provider_transfer_id"):
        assert private not in dumped
    assert "SUBMISSION_BLOCKED" not in [entry.state for entry in detail.history]


# ----- HTTP authorization -------------------------------------------------


@pytest.fixture
def http(monkeypatch):
    state: dict[str, User] = {}

    async def override_user() -> User:
        return state["user"]

    async def override_db():
        yield MagicMock()

    async def fake_context(self, user, brand_key="breero"):
        role, department, _ = DEFAULT_ACCESS[user.role]
        return PortalContext(
            user=UserRead.model_validate(user),
            brand_key=brand_key,
            dashboard_path="/",
            roles=[role],
            departments=[department],
            permissions=sorted(DEFAULT_PERMISSIONS[role]),
            assignments=[],
            identity_mode="local",
        )

    monkeypatch.setattr(AccessService, "context", fake_context)
    app.dependency_overrides[current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    try:
        yield state, TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("role", [UserRole.customer, UserRole.vendor_admin, UserRole.technician,
                                  UserRole.operations])
@pytest.mark.parametrize("path", [
    "/api/v1/finance/status",
    "/api/v1/finance/payout-batches",
    f"/api/v1/finance/payout-batches/{uuid.uuid4()}",
    "/api/v1/finance/earnings/summary",
    "/api/v1/finance/exceptions",
    "/api/v1/finance/payments",
    "/api/v1/finance/refunds",
])
def test_admin_finance_reads_require_finance_or_admin(http, role, path) -> None:
    state, client = http
    state["user"] = make_user(role)
    assert client.get(path).status_code == 403


@pytest.mark.parametrize("role", [UserRole.customer, UserRole.finance, UserRole.admin,
                                  UserRole.technician])
def test_provider_finance_requires_provider_permission(http, role) -> None:
    state, client = http
    state["user"] = make_user(role)
    assert client.get("/api/v1/provider/finance/earnings").status_code == 403


def test_provider_vendor_id_query_is_ignored(http, monkeypatch) -> None:
    state, client = http
    user = make_user(UserRole.vendor_admin)
    state["user"] = user
    earnings = AsyncMock(return_value=EarningPage(items=[], total=0, page=1, page_size=50))
    monkeypatch.setattr(ProviderFinanceService, "earnings", earnings)
    response = client.get(
        "/api/v1/provider/finance/earnings", params={"vendor_id": str(uuid.uuid4())}
    )
    assert response.status_code == 200
    args, kwargs = earnings.await_args
    assert args == (user,)
    assert "vendor_id" not in kwargs


def test_disabled_payout_commands_are_not_routable(http, monkeypatch) -> None:
    state, client = http
    state["user"] = make_user(UserRole.finance)
    for name in ("create_batch", "approve_batch", "submit_batch"):
        monkeypatch.setattr(FinanceService, name, AsyncMock(side_effect=AssertionError))
    batch = uuid.uuid4()
    assert client.post("/api/v1/finance/payout-batches", json={"currency": "USD"}).status_code == 405
    assert client.post(f"/api/v1/finance/payout-batches/{batch}/approve").status_code == 404
    assert client.post(f"/api/v1/finance/payout-batches/{batch}/submit").status_code == 404
