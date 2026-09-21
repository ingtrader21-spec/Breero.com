import uuid
from types import SimpleNamespace
from typing import cast

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.domains.auth.access_service import DEFAULT_PERMISSIONS
from app.domains.auth.dependencies import current_user
from app.domains.auth.models import (
    AccessAssignment,
    AccessRole,
    Department,
    RolePermission,
    TenantScope,
    User,
    UserPermission,
    UserRole,
)
from app.domains.common.outbox import AuditLog
from app.domains.finance.models import EarningStatus, PayoutStatus, VendorEarning
from app.domains.finance.repository import FinanceRepository
from app.domains.finance.service import FinanceService
from app.domains.portal.service import PortalReadService
from app.main import app


def test_portal_and_finance_read_contracts_are_present_with_payouts_disabled() -> None:
    assert settings.payout_enabled is False
    paths = app.openapi()["paths"]
    for path in (
        "/api/v1/portal/provider/overview",
        "/api/v1/portal/provider/jobs",
        "/api/v1/portal/provider/workers",
        "/api/v1/portal/provider/credentials",
        "/api/v1/portal/provider/earnings",
        "/api/v1/portal/provider/payout-batches",
        "/api/v1/portal/operations/overview",
        "/api/v1/portal/admin/overview",
        "/api/v1/portal/admin/audit",
        "/api/v1/finance/vendors",
        "/api/v1/finance/compensation-plans",
        "/api/v1/finance/earnings",
        "/api/v1/finance/payout-batches",
    ):
        assert "get" in paths[path]


def test_provider_default_access_is_read_scoped_to_its_own_resources() -> None:
    permissions = DEFAULT_PERMISSIONS[AccessRole.vendor_admin]
    assert {
        "provider.services.read",
        "provider.skills.read",
        "provider.jobs.read",
        "provider.workers.read",
        "provider.credentials.read",
        "provider.earnings.read",
        "provider.payouts.read",
    }.issubset(permissions)
    assert "finance.payouts.read" not in permissions
    assert "ops.dispatch.manage" not in permissions


def test_effective_capabilities_report_payouts_disabled() -> None:
    capabilities = PortalReadService.capabilities()
    assert capabilities.payouts is False
    assert capabilities.automatic_assignment is False


ADMIN_OVERVIEW_PERMISSIONS = (
    "admin.capabilities.read",
    "admin.audit.read",
    "admin.access.manage",
    "admin.integrations.read",
    "ops.dispatch.read",
    "ops.bookings.read",
    "ops.providers.read",
    "ops.customers.read",
    "finance.ledger.read",
    "finance.payouts.read",
)


class AdminOverviewSession:
    """Keep access resolution and the read model real; replace only database I/O."""

    def __init__(self) -> None:
        self.assignments: list[AccessAssignment] = []
        self.role_permissions: list[RolePermission] = []
        self.user_permissions: list[UserPermission] = []
        self.overview_reads = 0

    async def scalar(self, query):
        if query.get_final_froms()[0].name == "access_profiles":
            return None
        self.overview_reads += 1
        return 7

    async def scalars(self, query):
        entity = query.column_descriptions[0]["entity"]
        rows = {
            AccessAssignment: self.assignments,
            RolePermission: self.role_permissions,
            UserPermission: self.user_permissions,
            AuditLog: [],
        }[entity]
        if entity is AuditLog:
            self.overview_reads += 1
        return SimpleNamespace(all=lambda: rows)

    async def execute(self, query):
        self.overview_reads += 1
        rows = (
            [(EarningStatus.PENDING, "USD", 2, 15000)]
            if query.column_descriptions[0]["entity"] is VendorEarning
            else []
        )
        return SimpleNamespace(all=lambda: rows)


@pytest.fixture
def admin_overview_client(monkeypatch):
    actor = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        password_hash="unused",
        full_name="Restricted Admin",
        role=UserRole.admin,
        is_active=True,
        email_verified=True,
    )
    session = AdminOverviewSession()

    async def override_user():
        return actor

    async def override_db():
        yield session

    monkeypatch.setitem(app.dependency_overrides, current_user, override_user)
    monkeypatch.setitem(app.dependency_overrides, get_db, override_db)
    return TestClient(app), session, actor


def test_admin_overview_rejects_default_admin_before_reading_composite(admin_overview_client):
    client, session, _ = admin_overview_client

    response = client.get("/api/v1/portal/admin/overview")

    assert response.status_code == 403
    assert response.json() == {"detail": "Insufficient permissions"}
    assert session.overview_reads == 0


@pytest.mark.parametrize("denied_permission", ADMIN_OVERVIEW_PERMISSIONS)
def test_admin_overview_honors_each_user_permission_deny(
    admin_overview_client, denied_permission
):
    client, session, actor = admin_overview_client
    session.role_permissions = [
        RolePermission(role_key="admin", permission=permission, allow=True)
        for permission in ADMIN_OVERVIEW_PERMISSIONS
    ]
    session.user_permissions = [
        UserPermission(
            user_id=actor.id, brand_key="breero", permission=denied_permission, allow=False
        )
    ]

    response = client.get("/api/v1/portal/admin/overview")

    assert response.status_code == 403
    assert response.json() == {"detail": "Insufficient permissions"}
    assert session.overview_reads == 0


@pytest.mark.parametrize("access", ["explicit_grants", "superadmin"])
def test_admin_overview_allows_complete_access_with_payouts_disabled(
    admin_overview_client, access
):
    client, session, actor = admin_overview_client
    if access == "superadmin":
        session.assignments = [
            AccessAssignment(
                user_id=actor.id,
                brand_key="breero",
                role_key="superadmin",
                department=Department.administration.value,
                tenant_scope=TenantScope.global_.value,
                vendor_id=None,
                active=True,
                is_primary=True,
            )
        ]
    else:
        session.user_permissions = [
            UserPermission(
                user_id=actor.id, brand_key="breero", permission=permission, allow=True
            )
            for permission in ADMIN_OVERVIEW_PERMISSIONS
        ]

    response = client.get("/api/v1/portal/admin/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["users_total"] == 7
    assert payload["customers_total"] == 7
    assert payload["service_zones_total"] == 7
    assert payload["earnings"] == [
        {"status": "PENDING", "currency": "USD", "count": 2, "amount_minor": 15000}
    ]
    assert payload["capabilities"]["payouts"] is False
    assert payload["outbox"] == []
    assert payload["recent_audit"] == []


class FakeSession:
    def add(self, _value) -> None:
        pass

    async def commit(self) -> None:
        pass

    async def refresh(self, _value) -> None:
        pass


class FakeRepository:
    def __init__(self, batch) -> None:
        self.batch = batch

    async def get_batch(self, _batch_id, lock=False):
        return self.batch


@pytest.mark.asyncio
async def test_batch_reviewer_cannot_approve_same_payout(monkeypatch) -> None:
    actor_id = uuid.uuid4()
    batch = SimpleNamespace(
        id=uuid.uuid4(),
        status=PayoutStatus.PENDING_APPROVAL,
        reviewed_by=actor_id,
    )
    service = FinanceService(cast(AsyncSession, FakeSession()))
    service.repo = cast(FinanceRepository, FakeRepository(batch))
    monkeypatch.setattr(settings, "payout_enabled", True)

    with pytest.raises(HTTPException) as exc_info:
        await service.approve_batch(batch.id, actor_id)

    assert exc_info.value.status_code == 409
    assert "reviewer" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_batch_approver_cannot_submit_same_payout(monkeypatch) -> None:
    actor_id = uuid.uuid4()
    batch = SimpleNamespace(
        id=uuid.uuid4(),
        status=PayoutStatus.APPROVED,
        approved_by=actor_id,
        provider_transfer_id=None,
    )
    service = FinanceService(cast(AsyncSession, FakeSession()))
    service.repo = cast(FinanceRepository, FakeRepository(batch))
    monkeypatch.setattr(settings, "payout_enabled", True)

    with pytest.raises(HTTPException) as exc_info:
        await service.submit_batch(batch.id, actor_id)

    assert exc_info.value.status_code == 409
    assert "approver" in str(exc_info.value.detail).lower()

@pytest.mark.asyncio
@pytest.mark.parametrize("legacy_role,effective_roles,allowed", [
    ("admin", [], False),
    ("operations", [AccessRole.finance], True),
])
async def test_payout_commands_use_effective_membership(monkeypatch, legacy_role, effective_roles, allowed):
    from unittest.mock import AsyncMock

    from app.api.v1.finance import payout_command_actor
    from app.domains.auth.access_service import AccessService

    monkeypatch.setattr(AccessService, "context", AsyncMock(return_value=SimpleNamespace(roles=effective_roles)))
    monkeypatch.setattr(settings, "payout_enabled", True)
    actor = SimpleNamespace(role=legacy_role)
    if allowed:
        assert await payout_command_actor(actor, AsyncMock()) is actor
    else:
        with pytest.raises(HTTPException) as error:
            await payout_command_actor(actor, AsyncMock())
        assert error.value.status_code == 404
