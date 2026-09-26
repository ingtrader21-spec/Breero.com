import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from app.api.v1 import audit as audit_api
from app.core.errors import DomainError
from app.db.session import get_db
from app.domains.audit import context as audit_context
from app.domains.audit.catalog import (
    ACCESS_DENIED_ACTION,
    AuditCategory,
    AuditResult,
    categorize,
    is_security_event,
)
from app.domains.audit.enrichment import enrich
from app.domains.audit.redaction import REDACTED, project_metadata, scrub_for_storage
from app.domains.audit.repository import AuditQuery, AuditRepository, category_clause
from app.domains.audit.service import (
    MAX_WINDOW,
    decode_cursor,
    encode_cursor,
    resolve_window,
    to_detail,
)
from app.domains.auth import dependencies
from app.domains.auth.access_service import DEFAULT_PERMISSIONS
from app.domains.auth.models import AccessRole, User, UserRole
from app.domains.common.outbox import AuditLog
from app.main import app

NOW = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)
# Secret-shaped fixtures are assembled at runtime so repository secret scanners do not
# flag the test source itself.
RAW_TOKEN = ".".join(["ey" + "JhbGciOiJIUzI1NiJ9", "ey" + "JzdWIiOiIxMjM0NTY3ODkwIn0", "c2lnbmF0dXJl"])
STRIPE_LIKE_KEY = "_".join(["sk", "live", "abcdefghijklmnop"])


def make_user(role: UserRole) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4().hex}@example.com",
        password_hash="disabled",
        full_name="Audit Test",
        role=role,
        is_active=True,
        email_verified=True,
    )


def make_row(**overrides) -> AuditLog:
    values = {
        "id": uuid.uuid4(),
        "actor_id": uuid.uuid4(),
        "actor_type": "admin",
        "action": "payout.approve",
        "resource_type": "payout_batch",
        "resource_id": uuid.uuid4(),
        "metadata_json": {"status": "APPROVED"},
        "created_at": NOW,
        "result": "success",
        "request_id": "req-1",
        "correlation_id": "corr-1",
        "source_ip_hash": "a" * 64,
        "vendor_id": None,
    }
    values.update(overrides)
    return AuditLog(**values)


def query(**overrides) -> AuditQuery:
    values = {"occurred_from": NOW - timedelta(days=30), "occurred_to": NOW}
    values.update(overrides)
    return AuditQuery(**values)


# --- taxonomy ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("action", "category"),
    [
        (ACCESS_DENIED_ACTION, AuditCategory.access_denied),
        ("auth.login", AuditCategory.auth_lifecycle),
        ("auth.password.reset", AuditCategory.auth_lifecycle),
        ("access.assignments.replace", AuditCategory.access_change),
        ("admin.user.provision", AuditCategory.access_change),
        ("admin.user.disable", AuditCategory.access_change),
        ("service_zone.update", AuditCategory.privileged_admin),
        ("postal_code.import", AuditCategory.privileged_admin),
        ("provider.onboarding.approve", AuditCategory.provider_decision),
        ("provider.onboarding.reject", AuditCategory.provider_decision),
        ("assignment.create", AuditCategory.dispatch),
        ("manual_dispatch.update", AuditCategory.dispatch),
        ("payout.submit", AuditCategory.finance),
        ("integration.retry", AuditCategory.integration),
        ("privacy_request.received", AuditCategory.privacy),
        ("booking.cancel", AuditCategory.domain),
        ("provider.service.select", AuditCategory.domain),
    ],
)
def test_actions_map_to_stable_categories(action: str, category: AuditCategory) -> None:
    assert categorize(action) == category


def test_security_view_membership() -> None:
    assert is_security_event("payout.approve", "success")
    assert is_security_event("payout.submit", "success")
    assert not is_security_event("payout.review", "success")
    assert is_security_event("integration.retry", "success")
    assert is_security_event("provider.onboarding.reject", "success")
    assert is_security_event("booking.cancel", "failure")
    assert not is_security_event("booking.cancel", "success")


def test_category_sql_escapes_like_wildcards_and_applies_precedence() -> None:
    sql = str(
        category_clause(AuditCategory.privileged_admin).compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )
    # "_" in "service_zone." must not act as a single-character wildcard.
    assert "service/_zone." in sql and "ESCAPE '/'" in sql
    assert "NOT" in sql  # earlier categories are excluded (first match wins)
    domain_sql = str(category_clause(AuditCategory.domain).compile(dialect=postgresql.dialect()))
    assert domain_sql.startswith("NOT")


def test_search_query_is_bounded_and_keyset_ordered() -> None:
    sql = str(
        AuditRepository.build(
            query(actor_id=uuid.uuid4(), action_prefix="payout.", security_only=True)
        ).compile(dialect=postgresql.dialect())
    )
    assert "audit_logs.created_at >=" in sql and "audit_logs.created_at <" in sql
    assert "audit_logs.actor_id =" in sql
    assert "audit_logs.result !=" in sql


# --- redaction --------------------------------------------------------------------


def test_storage_scrub_redacts_secret_keys_and_token_values_recursively() -> None:
    scrubbed = scrub_for_storage(
        {
            "token": "abc",
            "nested": {"api_key": "k", "Authorization": "Bearer abcdefghijkl", "ok": 1},
            "items": [{"password": "p"}, RAW_TOKEN],
            "status": "APPROVED",
        }
    )
    assert scrubbed["token"] == REDACTED
    assert scrubbed["nested"] == {"api_key": REDACTED, "Authorization": REDACTED, "ok": 1}
    assert scrubbed["items"] == [{"password": REDACTED}, REDACTED]
    assert scrubbed["status"] == "APPROVED"


def test_read_projection_is_allowlist_only_and_bounded() -> None:
    projected = project_metadata(
        {
            "status": "APPROVED",
            "email": "person@example.com",
            "note": "free text",
            "previous_error": "odoo failed token=abc",
            "reason": "customer said something personal",
            "token": RAW_TOKEN,
            "role": "Bearer abcdefghijklmnop",
            "brand_key": "owner@example.com",
            "vendor_id": {"nested": "dropped"},
            "new_roles": ["admin"] * 50,
            "version": 3,
        }
    )
    assert projected == {
        "brand_key": REDACTED,
        "new_roles": ["admin"] * 20,
        "role": REDACTED,
        "status": "APPROVED",
        "version": 3,
    }


def test_detail_never_exposes_raw_metadata_secrets_or_full_source_hash() -> None:
    row = make_row(
        metadata_json={
            "status": "APPROVED",
            "token": RAW_TOKEN,
            "email": "person@example.com",
            "previous_error": "password=hunter2",
        }
    )
    detail = to_detail(row)
    body = detail.model_dump_json()
    assert RAW_TOKEN not in body
    assert "person@example.com" not in body
    assert "hunter2" not in body
    assert "a" * 64 not in body
    assert detail.source_fingerprint == "a" * 16
    assert detail.metadata == {"status": "APPROVED"}
    assert detail.metadata_withheld_keys == 3


# --- enrichment -------------------------------------------------------------------


def test_enrichment_copies_request_context_and_never_stores_raw_ip() -> None:
    token = audit_context.bind_request_context(
        request_id="req-42", correlation_id="corr-42", client_ip="203.0.113.9"
    )
    try:
        vendor_id = uuid.uuid4()
        row = AuditLog(
            actor_id=uuid.uuid4(),
            action="assignment.create",
            resource_type="job",
            resource_id=uuid.uuid4(),
            metadata_json={"vendor_id": str(vendor_id), "token": "secret"},
            created_at=NOW,
        )
        enrich(row)
    finally:
        audit_context.reset_request_context(token)
    assert row.request_id == "req-42"
    assert row.correlation_id == "corr-42"
    assert row.source_ip_hash and len(row.source_ip_hash) == 64
    assert "203.0.113.9" not in row.source_ip_hash
    assert row.vendor_id == vendor_id
    assert row.result == "success"
    assert row.metadata_json["token"] == REDACTED


def test_enrichment_keeps_explicit_values_and_derives_vendor_resource() -> None:
    token = audit_context.bind_request_context(
        request_id="req", correlation_id="corr", client_ip=None
    )
    try:
        vendor_id = uuid.uuid4()
        row = AuditLog(
            action="provider_credential.update",
            resource_type="vendor",
            resource_id=vendor_id,
            metadata_json={},
            created_at=NOW,
            result="denied",
            correlation_id="explicit",
        )
        enrich(row)
    finally:
        audit_context.reset_request_context(token)
    assert row.correlation_id == "explicit"
    assert row.result == "denied"
    assert row.source_ip_hash is None
    assert row.vendor_id == vendor_id


def test_source_hash_is_keyed_and_stable() -> None:
    first = audit_context.hash_source_ip("198.51.100.7")
    assert first == audit_context.hash_source_ip("198.51.100.7")
    assert first != audit_context.hash_source_ip("198.51.100.8")
    assert audit_context.hash_source_ip("unknown") is None
    assert first != hashlib.sha256(b"198.51.100.7").hexdigest()


# --- window and cursor ------------------------------------------------------------


def test_window_defaults_and_bounds() -> None:
    lower, upper = resolve_window(None, None, now=NOW)
    assert (lower, upper) == (NOW - timedelta(days=30), NOW)
    with pytest.raises(DomainError) as naive:
        resolve_window(datetime(2026, 9, 1), None, now=NOW)
    assert naive.value.status_code == 422
    with pytest.raises(DomainError):
        resolve_window(NOW, NOW - timedelta(days=1))
    with pytest.raises(DomainError) as wide:
        resolve_window(NOW - MAX_WINDOW - timedelta(seconds=1), NOW)
    assert wide.value.code == "AUDIT_FILTER_INVALID"


def test_cursor_round_trip_pins_window_and_rejects_foreign_searches() -> None:
    original = query(action="payout.approve")
    row = make_row(created_at=NOW - timedelta(hours=1))
    cursor = encode_cursor(row, original)

    drifted = query(
        action="payout.approve",
        occurred_from=NOW - timedelta(days=29),
        occurred_to=NOW + timedelta(minutes=5),
    )
    pinned, position = decode_cursor(cursor, drifted)
    assert (pinned.occurred_from, pinned.occurred_to) == (
        original.occurred_from,
        original.occurred_to,
    )
    assert position == (row.created_at, row.id)

    with pytest.raises(DomainError) as foreign:
        decode_cursor(cursor, query(action="payout.submit"))
    assert foreign.value.code == "AUDIT_CURSOR_INVALID"
    with pytest.raises(DomainError):
        decode_cursor(cursor, query(action="payout.approve", security_only=True))
    for garbage in ("not-base64!!", "e30=", cursor[:-4]):
        with pytest.raises(DomainError):
            decode_cursor(garbage, original)


# --- authorization and isolation ---------------------------------------------------


def test_only_admin_roles_hold_audit_read_permission() -> None:
    holders = {
        role
        for role, permissions in DEFAULT_PERMISSIONS.items()
        if "admin.audit.read" in permissions or "*" in permissions
    }
    assert holders == {AccessRole.admin, AccessRole.superadmin}


def test_audit_routes_are_read_only_and_permission_gated() -> None:
    paths = {
        path: set(methods)
        for path, methods in app.openapi()["paths"].items()
        if path.startswith("/api/v1/admin/audit")
    }
    assert paths == {
        "/api/v1/admin/audit/events": {"get"},
        "/api/v1/admin/audit/security-events": {"get"},
        "/api/v1/admin/audit/events/{event_id}": {"get"},
        "/api/v1/admin/audit/correlations/{correlation_id}": {"get"},
        "/api/v1/admin/audit/catalog": {"get"},
    }
    for route in audit_api.router.routes:
        calls = {dependency.call for dependency in route.dependant.dependencies}  # type: ignore[attr-defined]
        assert audit_api.can_read_audit in calls


class RecordingSession:
    def __init__(self, rows: list[AuditLog] | None = None) -> None:
        self.rows = rows or []
        self.added: list[object] = []
        self.commits = 0

    def add(self, value: object) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        return None

    async def scalar(self, _statement):
        return self.rows[0] if self.rows else None

    async def scalars(self, _statement):
        return SimpleNamespace(all=lambda: list(self.rows))


@pytest.fixture
def client():
    # No context manager: the lifespan would require live PostgreSQL and Redis.
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.parametrize("role", [UserRole.vendor_admin, UserRole.technician, UserRole.customer, UserRole.operations, UserRole.finance])
def test_non_admin_principals_are_denied_and_the_denial_is_audited(
    client: TestClient, monkeypatch, role: UserRole
) -> None:
    user = make_user(role)
    session = RecordingSession()

    class ProviderAccess:
        def __init__(self, _session) -> None:
            pass

        async def context(self, _user, _brand_key):
            return SimpleNamespace(roles=[], permissions=sorted(DEFAULT_PERMISSIONS[AccessRole(role.value)]))

    monkeypatch.setattr(dependencies, "AccessService", ProviderAccess)
    app.dependency_overrides[dependencies.current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: session

    response = client.get("/api/v1/admin/audit/events")

    assert response.status_code == 403
    denied = [item for item in session.added if isinstance(item, AuditLog)]
    assert len(denied) == 1
    assert denied[0].action == ACCESS_DENIED_ACTION
    assert denied[0].result == AuditResult.denied.value
    assert denied[0].actor_id == user.id
    assert denied[0].metadata_json["required"] == ["admin.audit.read"]
    assert session.commits == 1


def test_unauthenticated_requests_are_rejected(client: TestClient) -> None:
    assert client.get("/api/v1/admin/audit/events").status_code == 401
    assert client.get(f"/api/v1/admin/audit/events/{uuid.uuid4()}").status_code == 401


async def test_denial_audit_failure_never_turns_a_denial_into_an_allow(monkeypatch) -> None:
    user = make_user(UserRole.vendor_admin)

    class NoAccess:
        def __init__(self, _session) -> None:
            pass

        async def context(self, _user, _brand_key):
            return SimpleNamespace(roles=[], permissions=[])

    monkeypatch.setattr(dependencies, "AccessService", NoAccess)
    gate = dependencies.require_permissions("admin.audit.read")

    with pytest.raises(HTTPException) as exc_info:
        await gate(user, object())  # session without add/commit
    assert exc_info.value.status_code == 403


def _as_admin(session: RecordingSession) -> None:
    app.dependency_overrides[audit_api.can_read_audit] = lambda: make_user(UserRole.admin)
    app.dependency_overrides[get_db] = lambda: session


def test_admin_list_returns_summaries_without_metadata(client: TestClient) -> None:
    rows = [
        make_row(metadata_json={"token": RAW_TOKEN, "email": "p@example.com"}),
        make_row(action="auth.login", created_at=NOW - timedelta(minutes=1)),
    ]
    _as_admin(RecordingSession(rows))

    response = client.get(
        "/api/v1/admin/audit/events",
        params={
            "occurred_from": (NOW - timedelta(days=1)).isoformat(),
            "occurred_to": (NOW + timedelta(seconds=1)).isoformat(),
            "limit": 1,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["next_cursor"]
    item = body["items"][0]
    assert set(item) == {
        "id", "occurred_at", "category", "action", "result", "actor", "resource",
        "vendor_id", "request_id", "correlation_id", "security_relevant",
    }
    assert item["category"] == "finance" and item["security_relevant"] is True
    serialized = json.dumps(body)
    assert RAW_TOKEN not in serialized and "p@example.com" not in serialized


def test_admin_detail_and_trace_expose_only_safe_metadata(client: TestClient) -> None:
    row = make_row(metadata_json={"status": "APPROVED", "api_key": STRIPE_LIKE_KEY})
    _as_admin(RecordingSession([row]))

    detail = client.get(f"/api/v1/admin/audit/events/{row.id}")
    trace = client.get("/api/v1/admin/audit/correlations/corr-1")

    assert detail.status_code == 200
    assert detail.json()["metadata"] == {"status": "APPROVED"}
    assert "sk_live" not in detail.text
    assert trace.status_code == 200
    assert trace.json()["truncated"] is False
    assert [item["id"] for item in trace.json()["items"]] == [str(row.id)]
    assert "sk_live" not in trace.text


def test_admin_detail_missing_event_is_404(client: TestClient) -> None:
    _as_admin(RecordingSession([]))
    response = client.get(f"/api/v1/admin/audit/events/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "AUDIT_EVENT_NOT_FOUND"


@pytest.mark.parametrize(
    ("params", "status", "code"),
    [
        ({"occurred_from": "2026-09-01T00:00:00"}, 422, "AUDIT_FILTER_INVALID"),
        (
            {"occurred_from": "2024-01-01T00:00:00Z", "occurred_to": "2026-01-01T00:00:00Z"},
            422,
            "AUDIT_FILTER_INVALID",
        ),
        ({"cursor": "garbage"}, 400, "AUDIT_CURSOR_INVALID"),
        ({"action": "payout.approve", "action_prefix": "payout."}, 422, "AUDIT_FILTER_INVALID"),
    ],
)
def test_invalid_filters_are_rejected_with_stable_codes(
    client: TestClient, params: dict, status: int, code: str
) -> None:
    _as_admin(RecordingSession([]))
    response = client.get("/api/v1/admin/audit/events", params=params)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code


@pytest.mark.parametrize(
    "params",
    [{"limit": 0}, {"limit": 101}, {"action": "DROP TABLE"}, {"correlation_id": "bad id"}],
)
def test_out_of_contract_query_parameters_fail_validation(client: TestClient, params: dict) -> None:
    _as_admin(RecordingSession([]))
    assert client.get("/api/v1/admin/audit/events", params=params).status_code == 422


def test_catalog_publishes_retention_contract_without_purge(client: TestClient) -> None:
    _as_admin(RecordingSession([]))
    body = client.get("/api/v1/admin/audit/catalog").json()
    assert body["retention"]["automated_purge"] is False
    assert "access_denied" in body["security_categories"]
    assert body["limits"]["max_page_size"] == 100
