"""Fail-closed Keycloak role and account-state boundaries shared by the bearer and BFF paths."""

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, status

from app.domains.auth import keycloak
from app.domains.auth.dependencies import _keycloak_user
from app.domains.auth.models import User, UserRole
from tests.test_auth_access_contract import (
    FakeIdentityRepository,
    FakeIdentitySession,
    keycloak_claims,
)

ISSUER = "https://auth.codestra.co/realms/codestra"


def make_user(role: UserRole, *, active: bool = True, subject: str | None = None) -> User:
    return User(
        id=uuid.uuid4(),
        email="person@example.com",
        password_hash="disabled",
        full_name="Person",
        role=role,
        is_active=active,
        email_verified=True,
        keycloak_subject=subject,
    )


@pytest.fixture(autouse=True)
def _client_roles(monkeypatch) -> None:
    monkeypatch.setattr(
        keycloak,
        "settings",
        SimpleNamespace(keycloak_audience="breero-api", keycloak_client_id="breero-client-web"),
    )


def test_canonical_role_map_is_a_bijection_over_application_roles() -> None:
    assert set(keycloak.KEYCLOAK_ROLE_BY_USER_ROLE) == set(UserRole)
    assert len(set(keycloak.KEYCLOAK_ROLE_BY_USER_ROLE.values())) == len(UserRole)
    for role, name in keycloak.KEYCLOAK_ROLE_BY_USER_ROLE.items():
        assert keycloak.ROLE_MAP[name] is role


@pytest.mark.asyncio
@pytest.mark.parametrize("role", list(UserRole))
async def test_bearer_path_accepts_the_canonical_realm_role(role: UserRole) -> None:
    user = make_user(role)
    repository = FakeIdentityRepository(user)
    repository.subject_identity = SimpleNamespace(user_id=user.id)
    claims = keycloak_claims(roles=(keycloak.KEYCLOAK_ROLE_BY_USER_ROLE[role],))

    assert await _keycloak_user(claims, repository, FakeIdentitySession()) is user  # type: ignore[arg-type]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "token_roles"),
    [
        # A technician-level provider role must not unlock a provider-admin account.
        (UserRole.vendor_admin, ("breero_provider",)),
        (UserRole.admin, ("breero_dispatch", "breero_support")),
        (UserRole.operations, ("breero_client",)),
        # Legacy/non-canonical names are not accepted aliases.
        (UserRole.customer, ("breero_customer",)),
        (UserRole.technician, ("breero_worker",)),
        (UserRole.operations, ("breero_dispatcher",)),
        (UserRole.finance, ()),
    ],
)
async def test_bearer_path_rejects_wrong_or_legacy_realm_roles(
    role: UserRole, token_roles: tuple[str, ...]
) -> None:
    user = make_user(role)
    repository = FakeIdentityRepository(user)
    repository.subject_identity = SimpleNamespace(user_id=user.id)

    with pytest.raises(HTTPException) as exc_info:
        await _keycloak_user(  # type: ignore[arg-type]
            keycloak_claims(roles=token_roles), repository, FakeIdentitySession()
        )

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


class FakeLinkRepository:
    def __init__(self, user: User | None) -> None:
        self.user = user
        self.added: list[User] = []

    async def by_keycloak_subject(self, _issuer: str, subject: str) -> User | None:
        if self.user and self.user.keycloak_subject == subject:
            return self.user
        return None

    async def by_email(self, email: str) -> User | None:
        return self.user if self.user and self.user.email == email else None

    async def add(self, user: User) -> User:
        self.added.append(user)
        return user


class FlushSession:
    def __init__(self) -> None:
        self.flushes = 0

    async def flush(self) -> None:
        self.flushes += 1


def id_claims(*roles: str, subject: str = "kc-subject") -> dict:
    return {
        "iss": ISSUER,
        "sub": subject,
        "email": "person@example.com",
        "email_verified": True,
        "realm_access": {"roles": list(roles)},
    }


@pytest.mark.asyncio
async def test_identity_login_never_reactivates_a_deactivated_account(monkeypatch) -> None:
    user = make_user(UserRole.vendor_admin, active=False, subject="kc-subject")
    monkeypatch.setattr(keycloak, "UserRepository", lambda _session: FakeLinkRepository(user))
    session = FlushSession()

    with pytest.raises(HTTPException) as exc_info:
        await keycloak.link_identity(session, id_claims("breero_provider_admin"))  # type: ignore[arg-type]

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert user.is_active is False
    assert session.flushes == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "realm_role",
    ["breero_admin", "breero_dispatch", "breero_support", "breero_provider_admin", "breero_provider"],
)
async def test_identity_login_does_not_just_in_time_create_privileged_accounts(
    monkeypatch, realm_role: str
) -> None:
    repository = FakeLinkRepository(None)
    monkeypatch.setattr(keycloak, "UserRepository", lambda _session: repository)

    with pytest.raises(HTTPException) as exc_info:
        await keycloak.link_identity(FlushSession(), id_claims(realm_role))  # type: ignore[arg-type]

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert repository.added == []


@pytest.mark.asyncio
async def test_identity_login_creates_only_verified_customer_accounts(monkeypatch) -> None:
    repository = FakeLinkRepository(None)
    monkeypatch.setattr(keycloak, "UserRepository", lambda _session: repository)

    user = await keycloak.link_identity(FlushSession(), id_claims("breero_client"))  # type: ignore[arg-type]

    assert repository.added == [user]
    assert user.role is UserRole.customer
    assert user.keycloak_subject == "kc-subject"
    # The unusable local password must be a real Argon2 hash, not an un-awaited coroutine.
    assert isinstance(user.password_hash, str) and user.password_hash.startswith("$argon2")


@pytest.mark.asyncio
async def test_identity_login_without_any_breero_role_is_rejected(monkeypatch) -> None:
    user = make_user(UserRole.customer, subject="kc-subject")
    monkeypatch.setattr(keycloak, "UserRepository", lambda _session: FakeLinkRepository(user))

    with pytest.raises(HTTPException) as exc_info:
        await keycloak.link_identity(FlushSession(), id_claims("offline_access"))  # type: ignore[arg-type]

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
