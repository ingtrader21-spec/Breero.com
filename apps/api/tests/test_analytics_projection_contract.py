import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.policy_registry import get_endpoint_registry
from app.core.errors import DomainError
from app.domains.analytics.schemas import AnalyticsScopeKind
from app.domains.analytics.scope import (
    MARKETPLACE_PERMISSION,
    PROVIDER_PERMISSION,
    marketplace_scope_from_context,
)
from app.domains.analytics.service import MAX_WINDOW, resolve_window
from app.domains.auth.access_service import DEFAULT_PERMISSIONS
from app.domains.auth.models import AccessRole, Department, TenantScope
from app.domains.auth.schemas import AccessAssignmentRead, PortalContext, UserRead
from app.main import app

NOW = datetime(2026, 9, 23, 12, tzinfo=UTC)
PATHS = ("/api/v1/analytics/marketplace/metrics", "/api/v1/analytics/provider/metrics")


def context(
    permissions: list[str],
    *assignments: tuple[AccessRole, TenantScope],
) -> PortalContext:
    reads = [
        AccessAssignmentRead(
            role=role,
            department=Department.dispatch,
            tenant_scope=scope,
            vendor_id=uuid.uuid4() if scope == TenantScope.vendor else None,
        )
        for role, scope in assignments
    ]
    return PortalContext(
        user=UserRead(
            id=uuid.uuid4(),
            email="analyst@example.com",
            full_name="Analyst",
            role="operations",
            is_active=True,
            email_verified=True,
        ),
        brand_key="breero",
        dashboard_path="/ops",
        roles=[item.role for item in reads],
        departments=[item.department for item in reads],
        permissions=permissions,
        assignments=reads,
        identity_mode="local",
    )


def test_marketplace_scope_is_granted_to_internal_brand_or_global_assignments() -> None:
    for role, scope in (
        (AccessRole.ops_manager, TenantScope.brand),
        (AccessRole.admin, TenantScope.global_),
    ):
        resolved = marketplace_scope_from_context(context([MARKETPLACE_PERMISSION], (role, scope)))
        assert resolved.kind == AnalyticsScopeKind.marketplace
        assert resolved.vendor_id is None
    assert marketplace_scope_from_context(
        context(["*"], (AccessRole.superadmin, TenantScope.global_))
    ).kind == AnalyticsScopeKind.marketplace


@pytest.mark.parametrize(
    ("permissions", "assignments", "code"),
    [
        ([], [(AccessRole.ops_manager, TenantScope.brand)], "ANALYTICS_FORBIDDEN"),
        ([PROVIDER_PERMISSION], [(AccessRole.vendor_admin, TenantScope.vendor)], "ANALYTICS_FORBIDDEN"),
        # A permission override on a provider member must not widen to the marketplace.
        (
            [MARKETPLACE_PERMISSION],
            [(AccessRole.vendor_admin, TenantScope.vendor)],
            "ANALYTICS_SCOPE_DENIED",
        ),
        (
            [MARKETPLACE_PERMISSION],
            [(AccessRole.ops_manager, TenantScope.brand), (AccessRole.vendor_admin, TenantScope.vendor)],
            "ANALYTICS_SCOPE_DENIED",
        ),
        (["*"], [(AccessRole.superadmin, TenantScope.vendor)], "ANALYTICS_SCOPE_DENIED"),
        # Brand-scoped external roles (legacy default for customers/providers) are not internal.
        ([MARKETPLACE_PERMISSION], [(AccessRole.customer, TenantScope.brand)], "ANALYTICS_SCOPE_DENIED"),
        ([MARKETPLACE_PERMISSION], [(AccessRole.vendor_admin, TenantScope.brand)], "ANALYTICS_SCOPE_DENIED"),
        ([MARKETPLACE_PERMISSION], [], "ANALYTICS_SCOPE_DENIED"),
    ],
)
def test_marketplace_scope_fails_closed(permissions, assignments, code) -> None:
    with pytest.raises(DomainError) as raised:
        marketplace_scope_from_context(context(permissions, *assignments))
    assert raised.value.status_code == 403
    assert raised.value.code == code


def test_analytics_permissions_are_granted_only_to_intended_roles() -> None:
    marketplace = {role for role, granted in DEFAULT_PERMISSIONS.items() if MARKETPLACE_PERMISSION in granted}
    provider = {role for role, granted in DEFAULT_PERMISSIONS.items() if PROVIDER_PERMISSION in granted}
    assert marketplace == {AccessRole.ops_manager, AccessRole.admin}
    assert provider == {AccessRole.vendor_admin}


def test_window_defaults_to_thirty_days_ending_at_snapshot_time() -> None:
    window = resolve_window(None, None, NOW)
    assert (window.start, window.end) == (NOW - timedelta(days=30), NOW)


def test_window_is_normalized_to_utc() -> None:
    offset = datetime.fromisoformat("2026-09-01T00:00:00-05:00")
    window = resolve_window(offset, offset + timedelta(days=1), NOW)
    assert window.start == datetime(2026, 9, 1, 5, tzinfo=UTC)


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (NOW, NOW),
        (NOW, NOW - timedelta(seconds=1)),
        (NOW - MAX_WINDOW - timedelta(seconds=1), NOW),
        (datetime(2026, 9, 1), NOW),
        (None, datetime(2026, 9, 1)),
    ],
)
def test_invalid_windows_are_rejected(start, end) -> None:
    with pytest.raises(DomainError) as raised:
        resolve_window(start, end, NOW)
    assert raised.value.status_code == 422
    assert raised.value.code == "INVALID_ANALYTICS_WINDOW"


def test_analytics_routes_are_deny_by_default() -> None:
    client = TestClient(app)
    for path in PATHS:
        assert client.get(path).status_code == 401


def test_analytics_routes_are_read_only_and_registered_with_scoped_policies() -> None:
    schema = app.openapi()
    for path in PATHS:
        assert set(schema["paths"][path]) == {"get"}
    policies = {
        entry["path"]: entry
        for entry in get_endpoint_registry(app)["endpoints"]
        if entry["path"] in PATHS
    }
    assert set(policies) == set(PATHS)
    marketplace = policies[PATHS[0]]
    provider = policies[PATHS[1]]
    assert marketplace["permission"] == MARKETPLACE_PERMISSION
    assert provider["permission"] == PROVIDER_PERMISSION
    assert provider["tenant_scope"] == "provider-membership"
    for policy in policies.values():
        assert policy["method"] == "GET"
        assert policy["authentication"] == "bearer"
        assert policy["emitted_effect"] == "none"
        assert policy["resource_owner"] == "analytics"
