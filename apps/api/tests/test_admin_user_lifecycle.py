import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from app.core.errors import DomainError
from app.db.session import get_db
from app.domains.auth.access_service import DEFAULT_ACCESS, DEFAULT_PERMISSIONS, AccessService
from app.domains.auth.admin_schemas import (
    AdminUserAccessUpdate,
    AdminUserDetail,
    AdminUserList,
    AdminUserStatus,
    IdentityLinkSummary,
)
from app.domains.auth.admin_user_service import AdminUserService
from app.domains.auth.dependencies import current_user
from app.domains.auth.models import AccessRole, Department, Session, TenantScope, User, UserRole
from app.domains.auth.schemas import AccessAssignmentInput, PortalContext, UserRead
from app.domains.common.outbox import AuditLog
from app.main import app


def make_user(role: UserRole = UserRole.customer, *, active: bool = True) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4().hex}@example.com",
        password_hash="disabled",
        full_name="Lifecycle User",
        role=role,
        is_active=active,
        email_verified=True,
        credential_version=1,
    )


def context_for(user: User, *, roles=None, permissions=None) -> PortalContext:
    default_role, department, _ = DEFAULT_ACCESS[user.role]
    roles = roles if roles is not None else [default_role]
    return PortalContext(
        user=UserRead.model_validate(user),
        brand_key="breero",
        dashboard_path="/admin",
        roles=roles,
        departments=[department],
        permissions=sorted(
            permissions
            if permissions is not None
            else set().union(*(DEFAULT_PERMISSIONS[role] for role in roles))
        ),
        assignments=[],
        identity_mode="local",
    )


class Result:
    def __init__(self, rows=None, rowcount: int = 0) -> None:
        self._rows = rows or []
        self.rowcount = rowcount

    def all(self):
        return list(self._rows)


class FakeSession:
    def __init__(self, *, scalar_values=None, scalars_values=None, rowcount: int = 0) -> None:
        self.added: list[object] = []
        self.statements: list[object] = []
        self.commits = 0
        self._scalar_values = list(scalar_values or [])
        self._scalars_values = list(scalars_values or [])
        self._rowcount = rowcount

    def add(self, value: object) -> None:
        self.added.append(value)

    async def execute(self, statement):
        self.statements.append(statement)
        return Result(rowcount=self._rowcount)

    async def scalar(self, statement):
        self.statements.append(statement)
        return self._scalar_values.pop(0) if self._scalar_values else None

    async def scalars(self, statement):
        self.statements.append(statement)
        return Result(self._scalars_values.pop(0) if self._scalars_values else [])

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, _value) -> None:
        return None


def service_for(session: FakeSession, target: User, contexts: dict[uuid.UUID, PortalContext]):
    service = AdminUserService(session)  # type: ignore[arg-type]
    service._user = AsyncMock(return_value=target)  # type: ignore[method-assign]
    service.access.context = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda user, brand_key="breero": contexts[user.id]
    )
    service._detail = AsyncMock(return_value="detail")  # type: ignore[method-assign]
    return service


# ----- routes and HTTP authorization --------------------------------------


def test_admin_user_lifecycle_routes_are_registered() -> None:
    paths = app.openapi()["paths"]
    required = {
        "/api/v1/admin/users": {"get", "post"},
        "/api/v1/admin/users/{user_id}": {"get"},
        "/api/v1/admin/users/{user_id}/effective-access": {"get"},
        "/api/v1/admin/users/{user_id}/access": {"put"},
        "/api/v1/admin/users/{user_id}/disable": {"post"},
        "/api/v1/admin/users/{user_id}/reactivate": {"post"},
    }
    for path, methods in required.items():
        assert methods <= set(paths[path]), path


@pytest.fixture
def http(monkeypatch):
    state: dict[str, User] = {}

    async def override_user() -> User:
        return state["user"]

    async def override_db():
        yield MagicMock()

    async def fake_context(self, user, brand_key="breero"):
        return context_for(user)

    monkeypatch.setattr(AccessService, "context", fake_context)
    app.dependency_overrides[current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    try:
        yield state, TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "role", [UserRole.customer, UserRole.vendor_admin, UserRole.operations, UserRole.finance]
)
@pytest.mark.parametrize(
    "method,path_suffix,body",
    [
        ("get", "", None),
        ("get", "/{id}", None),
        ("get", "/{id}/effective-access", None),
        ("post", "/{id}/disable", {"reason": "policy breach"}),
        ("post", "/{id}/reactivate", {"reason": "cleared"}),
        ("put", "/{id}/access", {"assignments": [], "reason": "cleanup"}),
    ],
)
def test_non_admin_roles_cannot_manage_users(http, monkeypatch, role, method, path_suffix, body):
    state, client = http
    state["user"] = make_user(role)
    for name in ("list_users", "detail", "effective_access", "disable", "reactivate",
                 "replace_access"):
        monkeypatch.setattr(AdminUserService, name, AsyncMock(side_effect=AssertionError))
    path = "/api/v1/admin/users" + path_suffix.replace("{id}", str(uuid.uuid4()))
    response = getattr(client, method)(path, **({"json": body} if body else {}))
    assert response.status_code == 403


def test_admin_can_search_users_with_filters(http, monkeypatch) -> None:
    state, client = http
    state["user"] = make_user(UserRole.admin)
    listed = AsyncMock(return_value=AdminUserList(items=[], total=0, page=2, page_size=10))
    monkeypatch.setattr(AdminUserService, "list_users", listed)
    response = client.get(
        "/api/v1/admin/users",
        params={
            "q": "ann",
            "status": "disabled",
            "role": "finance",
            "access_role": "support",
            "page": 2,
            "page_size": 10,
        },
    )
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "page": 2, "page_size": 10}
    assert listed.await_args.kwargs == {
        "q": "ann",
        "role": UserRole.finance,
        "status": AdminUserStatus.disabled,
        "access_role": AccessRole.support,
        "page": 2,
        "page_size": 10,
    }


def test_disable_requires_reason(http) -> None:
    state, client = http
    state["user"] = make_user(UserRole.admin)
    response = client.post(f"/api/v1/admin/users/{uuid.uuid4()}/disable", json={})
    assert response.status_code == 422


def test_domain_errors_are_mapped(http, monkeypatch) -> None:
    state, client = http
    state["user"] = make_user(UserRole.admin)
    monkeypatch.setattr(
        AdminUserService,
        "detail",
        AsyncMock(side_effect=DomainError("USER_NOT_FOUND", "User not found.", 404)),
    )
    response = client.get(f"/api/v1/admin/users/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "USER_NOT_FOUND", "message": "User not found."}}


# ----- lifecycle service --------------------------------------------------


async def test_disable_revokes_breero_access_without_touching_identity_provider() -> None:
    actor, target = make_user(UserRole.admin), make_user(UserRole.customer)
    session = FakeSession(rowcount=3)
    service = service_for(
        session, target, {actor.id: context_for(actor), target.id: context_for(target)}
    )

    result = await service.disable(actor, target.id, "chargeback fraud", correlation_id="c-1")

    assert result == "detail"
    assert target.is_active is False
    assert target.credential_version == 2
    assert session.commits == 1
    [revoke] = session.statements
    assert revoke.table.name == Session.__table__.name
    [audit] = [item for item in session.added if isinstance(item, AuditLog)]
    assert audit.action == "admin.user.disable"
    assert audit.resource_id == target.id
    assert audit.actor_id == actor.id
    assert audit.metadata_json["reason"] == "chargeback fraud"
    assert audit.metadata_json["revoked_sessions"] == 3
    assert audit.metadata_json["identity_provider_action"] == "none"
    assert audit.metadata_json["correlation_id"] == "c-1"


async def test_admin_cannot_disable_self() -> None:
    actor = make_user(UserRole.admin)
    session = FakeSession()
    service = service_for(session, actor, {actor.id: context_for(actor)})
    with pytest.raises(DomainError) as error:
        await service.disable(actor, actor.id, "mistake")
    assert (error.value.code, error.value.status_code) == ("SELF_LIFECYCLE_FORBIDDEN", 409)
    assert actor.is_active is True
    assert session.commits == 0


async def test_only_superadmin_can_disable_privileged_administrator() -> None:
    actor, target = make_user(UserRole.admin), make_user(UserRole.admin)
    session = FakeSession()
    contexts = {actor.id: context_for(actor), target.id: context_for(target)}
    service = service_for(session, target, contexts)
    with pytest.raises(DomainError) as error:
        await service.disable(actor, target.id, "rotation")
    assert (error.value.code, error.value.status_code) == ("SUPERADMIN_REQUIRED", 403)
    assert target.is_active is True
    assert session.commits == 0

    contexts[actor.id] = context_for(actor, roles=[AccessRole.superadmin], permissions={"*"})
    await service.disable(actor, target.id, "rotation")
    assert target.is_active is False


async def test_disable_and_reactivate_reject_no_op_transitions() -> None:
    actor = make_user(UserRole.admin)
    disabled = make_user(UserRole.customer, active=False)
    session = FakeSession()
    service = service_for(
        session, disabled, {actor.id: context_for(actor), disabled.id: context_for(disabled)}
    )
    with pytest.raises(DomainError) as error:
        await service.disable(actor, disabled.id, "again")
    assert error.value.code == "USER_ALREADY_DISABLED"

    active = make_user(UserRole.customer)
    service = service_for(
        session, active, {actor.id: context_for(actor), active.id: context_for(active)}
    )
    with pytest.raises(DomainError) as error:
        await service.reactivate(actor, active.id, "again")
    assert error.value.code == "USER_ALREADY_ACTIVE"
    assert session.commits == 0


async def test_reactivate_restores_breero_access_and_is_audited() -> None:
    actor, target = make_user(UserRole.admin), make_user(UserRole.technician, active=False)
    session = FakeSession()
    service = service_for(
        session, target, {actor.id: context_for(actor), target.id: context_for(target)}
    )
    await service.reactivate(actor, target.id, "appeal accepted")
    assert target.is_active is True
    # Reactivation never restores revoked sessions or old tokens.
    assert target.credential_version == 1
    assert session.statements == []
    [audit] = session.added
    assert audit.action == "admin.user.reactivate"
    assert audit.metadata_json["identity_provider_action"] == "none"
    assert session.commits == 1


def _assignment(role: AccessRole, department: Department, **kwargs) -> AccessAssignmentInput:
    return AccessAssignmentInput(role=role, department=department, **kwargs)


async def test_admin_cannot_grant_superadmin() -> None:
    actor, target = make_user(UserRole.admin), make_user(UserRole.operations)
    session = FakeSession()
    service = service_for(
        session, target, {actor.id: context_for(actor), target.id: context_for(target)}
    )
    service.access.replace_assignments = AsyncMock()  # type: ignore[method-assign]
    data = AdminUserAccessUpdate(
        assignments=[_assignment(AccessRole.superadmin, Department.administration)],
        reason="promote",
    )
    with pytest.raises(DomainError) as error:
        await service.replace_access(actor, target.id, data)
    assert error.value.code == "SUPERADMIN_REQUIRED"
    service.access.replace_assignments.assert_not_awaited()
    assert session.added == []


async def test_vendor_scoped_access_requires_existing_vendor() -> None:
    actor, target = make_user(UserRole.admin), make_user(UserRole.vendor_admin)
    session = FakeSession(scalars_values=[[]])
    service = service_for(
        session, target, {actor.id: context_for(actor), target.id: context_for(target)}
    )
    service.access.replace_assignments = AsyncMock()  # type: ignore[method-assign]
    data = AdminUserAccessUpdate(
        assignments=[
            _assignment(
                AccessRole.vendor_admin,
                Department.provider,
                tenant_scope=TenantScope.vendor,
                vendor_id=uuid.uuid4(),
                is_primary=True,
            )
        ],
        reason="scope to vendor",
    )
    with pytest.raises(DomainError) as error:
        await service.replace_access(actor, target.id, data)
    assert (error.value.code, error.value.status_code) == ("VENDOR_NOT_FOUND", 422)
    service.access.replace_assignments.assert_not_awaited()


async def test_access_replacement_is_audited_in_same_transaction() -> None:
    actor, target = make_user(UserRole.admin), make_user(UserRole.operations)
    session = FakeSession()
    service = service_for(
        session, target, {actor.id: context_for(actor), target.id: context_for(target)}
    )
    order: list[str] = []

    async def replace(**kwargs):
        order.append("replace")
        assert any(isinstance(item, AuditLog) for item in session.added)

    service.access.replace_assignments = AsyncMock(side_effect=replace)  # type: ignore[method-assign]
    service._effective_access = AsyncMock(return_value="effective")  # type: ignore[method-assign]
    data = AdminUserAccessUpdate(
        assignments=[_assignment(AccessRole.support, Department.customer_support, is_primary=True)],
        reason="move to support",
    )
    assert await service.replace_access(actor, target.id, data) == "effective"
    assert order == ["replace"]
    [audit] = session.added
    assert audit.action == "admin.user.access.replace"
    assert audit.metadata_json["assignments"][0]["role"] == "support"


def test_access_update_rejects_duplicates_and_extra_fields() -> None:
    assignment = {"role": "support", "department": "customer_support"}
    with pytest.raises(ValidationError):
        AdminUserAccessUpdate.model_validate(
            {"assignments": [assignment, assignment], "reason": "dupe"}
        )
    with pytest.raises(ValidationError):
        AdminUserAccessUpdate.model_validate(
            {"assignments": [], "reason": "extra", "is_active": False}
        )


async def test_disabled_user_has_no_effective_permissions() -> None:
    target = make_user(UserRole.finance, active=False)
    session = FakeSession(scalar_values=[True])
    service = AdminUserService(session)  # type: ignore[arg-type]
    service.access.context = AsyncMock(return_value=context_for(target))  # type: ignore[method-assign]
    result = await service._effective_access(target, "breero")
    assert result.status == AdminUserStatus.disabled
    assert result.access.permissions  # assignments are retained for reactivation
    assert result.effective_permissions == []
    assert result.managed_profile is True


async def test_user_search_escapes_like_wildcards_and_filters_status() -> None:
    session = FakeSession(scalar_values=[0])
    service = AdminUserService(session)  # type: ignore[arg-type]
    result = await service.list_users(
        q="50%_off", status=AdminUserStatus.active, access_role=AccessRole.finance
    )
    assert result.total == 0
    count_sql = str(session.statements[0].compile(dialect=postgresql.dialect()))
    assert "lower(users.email) LIKE" in count_sql
    assert "access_assignments" in count_sql
    params = session.statements[0].compile(dialect=postgresql.dialect()).params
    assert "%50\\%\\_off%" in params.values()


def test_detail_never_exposes_identity_subject_or_credentials() -> None:
    assert "subject" not in IdentityLinkSummary.model_fields
    for field in ("password_hash", "credential_version"):
        assert field not in AdminUserDetail.model_fields
