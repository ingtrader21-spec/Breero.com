import asyncio
import hashlib
import hmac
import secrets
import time
import uuid
from typing import Any

import jwt
import structlog
from fastapi import HTTPException, status
from jwt.exceptions import MissingRequiredClaimError, PyJWKClientConnectionError, PyJWTError
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from starlette.concurrency import run_in_threadpool

from app.config import settings

PBKDF2_ITERATIONS = 600_000
LEGACY_PBKDF2_MAX_ITERATIONS = 1_000_000
TOKEN_TTL_SECONDS = 3600
REFRESH_TOKEN_TTL_SECONDS = 30 * 24 * 3600
LOCAL_JWT_ALGORITHM = "HS256"
LOCAL_JWT_ISSUER = "breero-api"
LOCAL_JWT_AUDIENCE = "breero-api"
KEYCLOAK_JWKS_TIMEOUT_SECONDS = 5
KEYCLOAK_JWKS_CACHE_SECONDS = 300
KEYCLOAK_JWKS_REFRESH_SECONDS = 240
CANONICAL_KEYCLOAK_ISSUER = "https://auth.codestra.co/realms/codestra"
KEYCLOAK_JWKS_URI = f"{CANONICAL_KEYCLOAK_ISSUER}/protocol/openid-connect/certs"
_STRICT_LOCAL_CLAIMS = frozenset({"iss", "aud", "nbf", "jti"})
# A rolling deploy can briefly have old and new workers minting tokens together.
# Keep the exact legacy shape valid for one access-token lifetime after this
# worker starts; every such token still expires within its normal one-hour TTL.
_LOCAL_TOKEN_COMPATIBILITY_DEADLINE = int(time.time()) + TOKEN_TTL_SECONDS

logger = structlog.get_logger()
PASSWORD_HASH = PasswordHash.recommended()
KEYCLOAK_JWKS_CLIENT = jwt.PyJWKClient(
    KEYCLOAK_JWKS_URI,
    # Keep the bounded JWK-set cache, but do not retain individual signing keys
    # in PyJWT's lifetime-unbounded LRU. A refreshed set must immediately stop
    # authorizing a removed or compromised kid without requiring worker restart.
    cache_keys=False,
    cache_jwk_set=True,
    lifespan=KEYCLOAK_JWKS_CACHE_SECONDS,
    timeout=KEYCLOAK_JWKS_TIMEOUT_SECONDS,
)


async def hash_password(password: str) -> str:
    """Hash a password with Argon2id outside the event-loop thread."""

    return await run_in_threadpool(PASSWORD_HASH.hash, password)


def _verify_legacy_pbkdf2(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations_text, salt_text, expected_text = encoded.split("$", 3)
        iterations = int(iterations_text)
        salt = bytes.fromhex(salt_text)
        expected = bytes.fromhex(expected_text)
    except (ValueError, TypeError):
        return False
    if (
        algorithm != "pbkdf2_sha256"
        or not 1 <= iterations <= LEGACY_PBKDF2_MAX_ITERATIONS
        or not salt
        or len(expected) != hashlib.sha256().digest_size
    ):
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return hmac.compare_digest(digest, expected)


def _verify_password_and_update(password: str, encoded: str) -> tuple[bool, str | None]:
    if encoded.startswith("pbkdf2_sha256$"):
        if not _verify_legacy_pbkdf2(password, encoded):
            return False, None
        return True, PASSWORD_HASH.hash(password)
    try:
        return PASSWORD_HASH.verify_and_update(password, encoded)
    except (UnknownHashError, ValueError, TypeError):
        return False, None


async def verify_password_and_update(
    password: str, encoded: str
) -> tuple[bool, str | None]:
    """Verify a password and return an Argon2id replacement hash when needed."""

    return await run_in_threadpool(_verify_password_and_update, password, encoded)


async def verify_password(password: str, encoded: str) -> bool:
    valid, _ = await verify_password_and_update(password, encoded)
    return valid


def new_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _secret() -> str:
    value = settings.jwt_secret
    if not value:
        raise RuntimeError("JWT_SECRET must be configured")
    return value


def create_access_token(
    user_id: uuid.UUID,
    role: str,
    ttl: int = TOKEN_TTL_SECONDS,
    credential_version: int = 1,
) -> str:
    now = int(time.time())
    claims = {
        "sub": str(user_id),
        "role": role,
        "cv": credential_version,
        "iat": now,
        "nbf": now,
        "exp": now + ttl,
        "iss": LOCAL_JWT_ISSUER,
        "aud": LOCAL_JWT_AUDIENCE,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(claims, _secret(), algorithm=LOCAL_JWT_ALGORITHM)


def _decode_legacy_local_token(token: str) -> dict[str, Any]:
    claims = jwt.decode(
        token,
        _secret(),
        algorithms=[LOCAL_JWT_ALGORITHM],
        options={
            "require": ["exp", "iat", "sub"],
            "verify_aud": False,
            "verify_iss": False,
        },
    )
    # Accept only the complete pre-migration shape during the bounded rolling
    # compatibility window. A token cannot extend its lifetime beyond the
    # historical one-hour contract.
    if _STRICT_LOCAL_CLAIMS.intersection(claims):
        raise jwt.InvalidTokenError("partially migrated local token")
    issued_at = int(claims["iat"])
    expires_at = int(claims["exp"])
    if (
        issued_at > _LOCAL_TOKEN_COMPATIBILITY_DEADLINE
        or expires_at <= issued_at
        or expires_at - issued_at > TOKEN_TTL_SECONDS
        or expires_at > _LOCAL_TOKEN_COMPATIBILITY_DEADLINE + TOKEN_TTL_SECONDS
    ):
        raise jwt.InvalidTokenError("legacy local token outside compatibility window")
    return claims


def _decode_local_access_token(token: str) -> dict[str, Any]:
    try:
        claims = jwt.decode(
            token,
            _secret(),
            algorithms=[LOCAL_JWT_ALGORITHM],
            issuer=LOCAL_JWT_ISSUER,
            audience=LOCAL_JWT_AUDIENCE,
            options={"require": ["exp", "iat", "sub", "iss", "aud", "nbf", "jti"]},
        )
    except MissingRequiredClaimError:
        claims = _decode_legacy_local_token(token)
    jti = claims.get("jti")
    if jti is not None and (not isinstance(jti, str) or not jti.strip()):
        raise jwt.InvalidTokenError("invalid jti")
    return claims


async def decode_access_token(token: str) -> dict[str, Any]:
    error = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    try:
        if settings.keycloak_enabled:
            return await decode_keycloak_access_token(token)
        return _decode_local_access_token(token)
    except HTTPException:
        raise
    except (PyJWTError, ValueError, TypeError) as exc:
        raise error from exc


def _validated_keycloak_issuer() -> str:
    issuer = settings.keycloak_issuer.rstrip("/")
    if issuer != CANONICAL_KEYCLOAK_ISSUER:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid identity issuer configuration",
        )
    return issuer


async def refresh_keycloak_jwks() -> None:
    """Refresh the shared JWKS cache without blocking the application loop."""

    await run_in_threadpool(lambda: KEYCLOAK_JWKS_CLIENT.get_jwk_set(refresh=True))


async def maintain_keycloak_jwks(stop: asyncio.Event) -> None:
    """Refresh signing keys at a bounded interval until application shutdown."""

    while not stop.is_set():
        try:
            await refresh_keycloak_jwks()
        except Exception as exc:
            logger.warning("keycloak_jwks_refresh_failed", error=type(exc).__name__)
        try:
            await asyncio.wait_for(
                stop.wait(),
                timeout=KEYCLOAK_JWKS_REFRESH_SECONDS,
            )
        except TimeoutError:
            continue


async def decode_keycloak_access_token(token: str) -> dict[str, Any]:
    invalid = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    issuer = _validated_keycloak_issuer()
    try:
        signing_key = await run_in_threadpool(
            KEYCLOAK_JWKS_CLIENT.get_signing_key_from_jwt,
            token,
        )
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.keycloak_audience,
            issuer=issuer,
            options={"require": ["exp", "iat", "sub"]},
        )
    except PyJWKClientConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Identity signing keys unavailable",
        ) from exc
    except PyJWTError as exc:
        raise invalid from exc
