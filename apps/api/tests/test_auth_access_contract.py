import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, status
from pydantic import ValidationError

from app.api.v1 import auth
from app.domains.auth.access_service import DASHBOARD_BY_ROLE, DEFAULT_ACCESS, DEFAULT_PERMISSIONS
from app.domains.auth.dependencies import _keycloak_user
from app.domains.auth.models import AccessRole, Department, TenantScope, User, UserRole
from app.domains.auth.schemas import (
    AccessAssignmentInput,
    AccessProfileUpdate,
    ForgotPasswordRequest,
    RegisterRequest,
)


class FakeIdentitySession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class FakeIdentityRepository:
    def __init__(self, user: User) -> None:
        self.user = user
        self.subject_identity = None
        self.user_identity = None
        self.added_identity = None
        self.email_lookups = 0

    async def identity_by_subject(self, _brand: str, _issuer: str, _subject: str):
        return self.subject_identity

    async def identity_by_user_issuer(self, _brand: str, _issuer: str, _user_id: uuid.UUID):
        return self.user_identity

    async def by_email(self, email: str):
        self.email_lookups += 1
        return self.user if email == self.user.email else None

    async def by_id(self, user_id: uuid.UUID):
        return self.user if user_id == self.user.id else None

    async def add_identity(self, identity):
        self.added_identity = identity
        return identity


def keycloak_claims(*, email: str = "person@example.com", subject: str = "kc-subject") -> dict:
    return {
        "sub": subject,
        "iss": "https://auth.codestra.co/realms/codestra",
        "email": email,
        "email_verified": True,
        "realm_access": {"roles": ["breero_customer"]},
    }


def test_every_coarse_user_role_has_default_portal_access() -> None:
    assert set(DEFAULT_ACCESS) == set(UserRole)
    for role, (access_role, department, scope) in DEFAULT_ACCESS.items():
        assert access_role in AccessRole
        assert department in Department
        assert scope in TenantScope
        assert DASHBOARD_BY_ROLE[access_role].startswith("/")
        assert DEFAULT_PERMISSIONS[access_role]
        assert role.value


def test_every_department_role_has_a_dashboard_and_permission_profile() -> None:
    assert set(DASHBOARD_BY_ROLE) == set(AccessRole)
    assert set(DEFAULT_PERMISSIONS) == set(AccessRole)


def test_vendor_scope_requires_vendor_id() -> None:
    with pytest.raises(ValidationError):
        AccessAssignmentInput(
            role=AccessRole.vendor_admin,
            department=Department.provider,
            tenant_scope=TenantScope.vendor,
        )


def test_non_vendor_scope_rejects_vendor_id() -> None:
    with pytest.raises(ValidationError):
        AccessAssignmentInput(
            role=AccessRole.operations,
            department=Department.dispatch,
            tenant_scope=TenantScope.brand,
            vendor_id=uuid.uuid4(),
        )


def test_access_profile_allows_only_one_primary_assignment() -> None:
    with pytest.raises(ValidationError):
        AccessProfileUpdate(
            assignments=[
                AccessAssignmentInput(
                    role=AccessRole.operations,
                    department=Department.dispatch,
                    is_primary=True,
                ),
                AccessAssignmentInput(
                    role=AccessRole.support,
                    department=Department.customer_support,
                    is_primary=True,
                ),
            ]
        )


def test_access_profile_rejects_duplicate_role_department() -> None:
    with pytest.raises(ValidationError):
        AccessProfileUpdate(
            assignments=[
                AccessAssignmentInput(
                    role=AccessRole.quality,
                    department=Department.quality,
                ),
                AccessAssignmentInput(
                    role=AccessRole.quality,
                    department=Department.quality,
                ),
            ]
        )


def test_local_credentials_are_disabled_when_keycloak_is_authoritative(monkeypatch) -> None:
    monkeypatch.setattr(auth, "settings", SimpleNamespace(keycloak_enabled=True))
    with pytest.raises(HTTPException) as exc_info:
        auth.local_auth_only()
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "identity provider" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_local_public_registration_is_blocked_when_keycloak_is_authoritative(
    monkeypatch,
) -> None:
    monkeypatch.setattr(auth, "settings", SimpleNamespace(keycloak_enabled=True))
    request = SimpleNamespace(headers={}, client=None)
    data = RegisterRequest(
        email="new-user@example.com",
        password="local-password-not-used",
        full_name="New User",
    )

    with pytest.raises(HTTPException) as exc_info:
        await auth.register(data, request, FakeIdentitySession(), None)  # type: ignore[arg-type]

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc_info.value.detail == "Public account registration is disabled"


@pytest.mark.asyncio
async def test_local_password_recovery_is_blocked_when_keycloak_is_authoritative(
    monkeypatch,
) -> None:
    monkeypatch.setattr(auth, "settings", SimpleNamespace(keycloak_enabled=True))

    with pytest.raises(HTTPException) as exc_info:
        await auth.forgot(
            ForgotPasswordRequest(email="person@example.com"),
            FakeIdentitySession(),  # type: ignore[arg-type]
            None,
        )

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "identity provider" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_keycloak_first_login_links_verified_subject_to_provisioned_user() -> None:
    user = User(
        id=uuid.uuid4(),
        email="person@example.com",
        password_hash="disabled",
        full_name="Person",
        role=UserRole.customer,
        is_active=True,
        email_verified=True,
    )
    repository = FakeIdentityRepository(user)
    session = FakeIdentitySession()

    resolved = await _keycloak_user(keycloak_claims(), repository, session)  # type: ignore[arg-type]

    assert resolved is user
    assert repository.added_identity is not None
    assert repository.added_identity.user_id == user.id
    assert repository.added_identity.subject == "kc-subject"
    assert session.commits == 1


@pytest.mark.asyncio
async def test_keycloak_linked_subject_remains_authoritative_after_email_change() -> None:
    user = User(
        id=uuid.uuid4(),
        email="person@example.com",
        password_hash="disabled",
        full_name="Person",
        role=UserRole.customer,
        is_active=True,
        email_verified=True,
    )
    repository = FakeIdentityRepository(user)
    repository.subject_identity = SimpleNamespace(user_id=user.id)
    session = FakeIdentitySession()

    resolved = await _keycloak_user(
        keycloak_claims(email="new-address@example.com"), repository, session  # type: ignore[arg-type]
    )

    assert resolved is user
    assert repository.email_lookups == 0
    assert session.commits == 0


@pytest.mark.asyncio
async def test_keycloak_rejects_new_subject_when_user_already_has_identity() -> None:
    user = User(
        id=uuid.uuid4(),
        email="person@example.com",
        password_hash="disabled",
        full_name="Person",
        role=UserRole.customer,
        is_active=True,
        email_verified=True,
    )
    repository = FakeIdentityRepository(user)
    repository.user_identity = SimpleNamespace(user_id=user.id, subject="different-subject")
    session = FakeIdentitySession()

    with pytest.raises(HTTPException) as exc_info:
        await _keycloak_user(keycloak_claims(), repository, session)  # type: ignore[arg-type]

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "Identity does not match" in str(exc_info.value.detail)
    assert session.commits == 0
