import hashlib
import time
import uuid
from unittest.mock import AsyncMock

import jwt
import pytest
from fastapi import HTTPException
from jwt.exceptions import PyJWKClientConnectionError

from app.config import settings
from app.domains.auth import security
from app.domains.auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    hash_token,
    new_opaque_token,
    verify_password,
    verify_password_and_update,
)


def legacy_pbkdf2_hash(password: str, *, iterations: int = 1_000) -> str:
    salt = bytes.fromhex("00112233445566778899aabbccddeeff")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


@pytest.mark.asyncio
async def test_password_hash_round_trip_uses_argon2id() -> None:
    encoded = await hash_password("a long secure password")
    assert encoded.startswith("$argon2id$")
    assert encoded != "a long secure password"
    assert await verify_password("a long secure password", encoded)
    assert not await verify_password("wrong password", encoded)


@pytest.mark.asyncio
async def test_legacy_pbkdf2_is_verified_and_upgraded() -> None:
    encoded = legacy_pbkdf2_hash("a long secure password")
    valid, updated = await verify_password_and_update("a long secure password", encoded)
    assert valid
    assert updated is not None
    assert updated.startswith("$argon2id$")
    assert await verify_password("a long secure password", updated)


@pytest.mark.asyncio
async def test_invalid_or_excessive_legacy_hash_is_rejected() -> None:
    encoded = legacy_pbkdf2_hash(
        "a long secure password",
        iterations=security.LEGACY_PBKDF2_MAX_ITERATIONS + 1,
    )
    assert not await verify_password("a long secure password", encoded)
    assert not await verify_password("password", "pbkdf2_sha256$broken")


@pytest.mark.asyncio
async def test_password_hashing_is_dispatched_to_threadpool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = AsyncMock(return_value="$argon2id$test")
    monkeypatch.setattr(security, "run_in_threadpool", runner)
    assert await hash_password("password") == "$argon2id$test"
    runner.assert_awaited_once_with(security.PASSWORD_HASH.hash, "password")


@pytest.mark.asyncio
async def test_access_token_round_trip_has_strict_registered_claims() -> None:
    user_id = uuid.uuid4()
    claims = await decode_access_token(create_access_token(user_id, "operations"))
    assert claims["sub"] == str(user_id)
    assert claims["role"] == "operations"
    assert claims["iss"] == security.LOCAL_JWT_ISSUER
    assert claims["aud"] == security.LOCAL_JWT_AUDIENCE
    assert claims["nbf"] == claims["iat"]
    assert uuid.UUID(claims["jti"])


@pytest.mark.asyncio
async def test_tampered_access_token_is_rejected() -> None:
    token = create_access_token(uuid.uuid4(), "customer")
    header, payload, signature = token.split(".")
    signature = ("A" if signature[0] != "A" else "B") + signature[1:]
    tampered = ".".join((header, payload, signature))
    with pytest.raises(HTTPException) as error:
        await decode_access_token(tampered)
    assert error.value.status_code == 401


@pytest.mark.asyncio
async def test_wrong_local_token_issuer_or_audience_is_rejected() -> None:
    token = create_access_token(uuid.uuid4(), "customer")
    claims = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[security.LOCAL_JWT_ALGORITHM],
        options={"verify_signature": False},
    )
    for claim, value in (("iss", "wrong-issuer"), ("aud", "wrong-audience")):
        changed = {**claims, claim: value}
        invalid = jwt.encode(
            changed,
            settings.jwt_secret,
            algorithm=security.LOCAL_JWT_ALGORITHM,
        )
        with pytest.raises(HTTPException) as error:
            await decode_access_token(invalid)
        assert error.value.status_code == 401


@pytest.mark.asyncio
async def test_exact_legacy_local_token_shape_survives_rolling_release() -> None:
    now = min(int(time.time()), security._LOCAL_TOKEN_COMPATIBILITY_DEADLINE)
    user_id = uuid.uuid4()
    token = jwt.encode(
        {
            "sub": str(user_id),
            "role": "customer",
            "cv": 3,
            "iat": now,
            "exp": now + 60,
        },
        settings.jwt_secret,
        algorithm=security.LOCAL_JWT_ALGORITHM,
    )
    claims = await decode_access_token(token)
    assert claims["sub"] == str(user_id)
    assert claims["cv"] == 3


@pytest.mark.asyncio
async def test_partially_migrated_local_token_is_not_accepted_as_legacy() -> None:
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "role": "customer",
            "cv": 1,
            "iat": now,
            "nbf": now,
            "exp": now + 60,
            "iss": security.LOCAL_JWT_ISSUER,
            "aud": security.LOCAL_JWT_AUDIENCE,
        },
        settings.jwt_secret,
        algorithm=security.LOCAL_JWT_ALGORITHM,
    )
    with pytest.raises(HTTPException) as error:
        await decode_access_token(token)
    assert error.value.status_code == 401


def test_keycloak_signing_key_cache_is_disabled() -> None:
    # PyJWT decorates get_signing_key with functools.lru_cache only when
    # cache_keys=True. The individual-key cache must remain disabled so a
    # refreshed JWK set immediately revokes a removed or compromised kid.
    assert not hasattr(security.KEYCLOAK_JWKS_CLIENT.get_signing_key, "cache_info")


@pytest.mark.asyncio
async def test_keycloak_uses_shared_bounded_jwks_client_off_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[object] = []

    class SigningKey:
        key = object()

    async def fake_run(function, *args):
        seen.append(getattr(function, "__self__", None))
        return SigningKey()

    monkeypatch.setattr(settings, "keycloak_issuer", security.CANONICAL_KEYCLOAK_ISSUER)
    monkeypatch.setattr(security, "run_in_threadpool", fake_run)
    monkeypatch.setattr(
        security.jwt,
        "decode",
        lambda *args, **kwargs: {"sub": "subject", "iss": security.CANONICAL_KEYCLOAK_ISSUER},
    )

    claims = await security.decode_keycloak_access_token("header.payload.signature")

    assert claims["sub"] == "subject"
    assert seen == [security.KEYCLOAK_JWKS_CLIENT]
    assert security.KEYCLOAK_JWKS_CLIENT.timeout == security.KEYCLOAK_JWKS_TIMEOUT_SECONDS


@pytest.mark.asyncio
async def test_keycloak_jwks_connection_failure_is_bounded_degradation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unavailable(*args, **kwargs):
        raise PyJWKClientConnectionError("unavailable")

    monkeypatch.setattr(settings, "keycloak_issuer", security.CANONICAL_KEYCLOAK_ISSUER)
    monkeypatch.setattr(security, "run_in_threadpool", unavailable)

    with pytest.raises(HTTPException) as error:
        await security.decode_keycloak_access_token("header.payload.signature")
    assert error.value.status_code == 503


def test_opaque_tokens_are_random_and_only_hashes_need_persisting() -> None:
    first, second = new_opaque_token(), new_opaque_token()
    assert first != second
    assert len(first) >= 32
    assert hash_token(first) != first
    assert len(hash_token(first)) == 64


@pytest.mark.asyncio
async def test_access_token_contains_credential_version() -> None:
    claims = await decode_access_token(
        create_access_token(uuid.uuid4(), "customer", credential_version=7)
    )
    assert claims["cv"] == 7
