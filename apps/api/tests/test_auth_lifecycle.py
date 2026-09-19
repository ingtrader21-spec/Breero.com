import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.domains.auth.models import (
    EmailVerificationToken,
    PasswordResetToken,
    Session,
    User,
    UserRole,
)
from app.domains.auth.schemas import LoginRequest
from app.domains.auth.security import verify_password
from app.domains.auth.service import AuthService

LEGACY_PASSWORD_HASH = (
    "pbkdf2_sha256$1000$00112233445566778899aabbccddeeff$"
    "d67d9d5c5d2a22e2f4ac35496d2e0589cf08978785ec4406f24314d9312230a1"
)


@pytest.fixture
def service() -> AuthService:
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()
    session.refresh = AsyncMock()
    result = AuthService(session)
    result.users = AsyncMock()
    return result


def user() -> User:
    return User(
        id=uuid.uuid4(),
        email="customer@example.com",
        full_name="Test Customer",
        password_hash=LEGACY_PASSWORD_HASH,
        role=UserRole.customer,
        is_active=True,
        email_verified=True,
        credential_version=1,
    )


@pytest.mark.asyncio
async def test_login_transparently_rehashes_legacy_password(service: AuthService) -> None:
    account = user()
    service.users.by_email.return_value = account

    result = await service.login(
        LoginRequest(email=account.email, password="old-password-123"),
        user_agent="pytest",
        ip="127.0.0.1",
    )

    assert result.user.id == account.id
    assert account.password_hash.startswith("$argon2id$")
    service.session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_refresh_rotates_previous_token(
    service: AuthService, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    account = user()
    old = Session(
        user_id=account.id,
        token_hash="hash",
        family_id=uuid.uuid4(),
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    service.users.session_by_hash.return_value = old
    service.users.by_id.return_value = account
    result = await service.refresh("refresh-token-that-is-long-enough")
    assert old.rotated_at is not None
    assert result.refresh_token != "refresh-token-that-is-long-enough"
    service.session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_refresh_token_reuse_revokes_family(service: AuthService) -> None:
    old = Session(
        user_id=uuid.uuid4(),
        token_hash="hash",
        family_id=uuid.uuid4(),
        expires_at=datetime.now(UTC) + timedelta(days=1),
        rotated_at=datetime.now(UTC),
    )
    service.users.session_by_hash.return_value = old
    with pytest.raises(HTTPException, match="reuse") as error:
        await service.refresh("refresh-token-that-is-long-enough")
    assert error.value.status_code == 401
    service.session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_expired_refresh_token_is_rejected(service: AuthService) -> None:
    expired = Session(
        user_id=uuid.uuid4(),
        token_hash="hash",
        family_id=uuid.uuid4(),
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    service.users.session_by_hash.return_value = expired

    with pytest.raises(HTTPException, match="expired") as error:
        await service.refresh("refresh-token-that-is-long-enough")

    assert error.value.status_code == 401
    assert expired.revoked_at is not None
    service.session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_logout_revokes_session(service: AuthService) -> None:
    active = Session(
        user_id=uuid.uuid4(),
        token_hash="hash",
        family_id=uuid.uuid4(),
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    service.users.session_by_hash.return_value = active
    await service.logout("refresh-token-that-is-long-enough")
    assert active.revoked_at is not None


@pytest.mark.asyncio
async def test_expired_password_reset_is_rejected(service: AuthService) -> None:
    service.users.reset_by_hash.return_value = PasswordResetToken(
        user_id=uuid.uuid4(),
        token_hash="hash",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    with pytest.raises(HTTPException, match="expired"):
        await service.reset_password("reset-token-that-is-long-enough", "new-password-123")


@pytest.mark.asyncio
async def test_valid_password_reset_invalidates_credentials(service: AuthService) -> None:
    account = user()
    token = PasswordResetToken(
        user_id=account.id,
        token_hash="hash",
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    service.users.reset_by_hash.return_value = token
    service.users.by_id.return_value = account
    await service.reset_password("reset-token-that-is-long-enough", "new-password-123")
    assert token.used_at is not None
    assert account.credential_version == 2
    assert await verify_password("new-password-123", account.password_hash)


@pytest.mark.asyncio
async def test_verification_replay_is_rejected(service: AuthService) -> None:
    service.users.verification_by_hash.return_value = EmailVerificationToken(
        user_id=uuid.uuid4(),
        token_hash="hash",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        used_at=datetime.now(UTC),
    )
    with pytest.raises(HTTPException, match="Invalid"):
        await service.verify_email("verification-token-that-is-long-enough")
