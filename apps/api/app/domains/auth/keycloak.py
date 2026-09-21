import hashlib
import secrets
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
import redis.asyncio as redis
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.domains.auth.models import User, UserRole
from app.domains.auth.repository import UserRepository
from app.domains.auth.security import hash_password

OIDC_COOKIE = "breero_oidc_transaction"
ROLE_MAP = {
    "breero_admin": UserRole.admin,
    "breero_dispatch": UserRole.operations,
    "breero_support": UserRole.finance,
    "breero_provider_admin": UserRole.vendor_admin,
    "breero_provider": UserRole.technician,
    "breero_client": UserRole.customer,
}


def _issuer() -> str:
    return settings.keycloak_issuer.rstrip("/")


async def discovery() -> dict[str, Any]:
    url = f"{_issuer()}/.well-known/openid-configuration"
    async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
        response = await client.get(url)
    response.raise_for_status()
    document = response.json()
    if document.get("issuer") != _issuer():
        raise HTTPException(503, "Identity provider issuer mismatch")
    return document


def create_transaction(return_to: str) -> tuple[str, str, str, str]:
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    destinations = {
        "/account": f"{settings.breero_web_url.rstrip('/')}/account",
        "/provider": settings.breero_provider_web_url.rstrip("/"),
        "/admin": settings.breero_admin_web_url.rstrip("/"),
    }
    safe_return = destinations.get(return_to, destinations["/account"])
    payload = {"state": state, "nonce": nonce, "verifier": verifier, "return_to": safe_return, "exp": int(time.time()) + 600}
    transaction = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return state, nonce, verifier, transaction


def read_transaction(raw: str | None, state: str) -> dict[str, Any]:
    try:
        value = jwt.decode(raw or "", settings.jwt_secret, algorithms=["HS256"], options={"require": ["exp", "state", "nonce", "verifier"]})
        if not secrets.compare_digest(str(value["state"]), state):
            raise ValueError("state mismatch")
        return value
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(400, "Invalid or expired login transaction") from exc


async def authorization_url(return_to: str) -> tuple[str, str]:
    document = await discovery()
    state, nonce, verifier, transaction = create_transaction(return_to)
    challenge = jwt.utils.base64url_encode(hashlib.sha256(verifier.encode()).digest()).decode()
    query = urlencode({"client_id": settings.keycloak_client_id, "redirect_uri": settings.keycloak_redirect_uri, "response_type": "code", "scope": "openid profile email", "state": state, "nonce": nonce, "code_challenge": challenge, "code_challenge_method": "S256"})
    return f"{document['authorization_endpoint']}?{query}", transaction


async def exchange_code(code: str, verifier: str, nonce: str) -> tuple[dict[str, Any], str, int]:
    document = await discovery()
    async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
        response = await client.post(document["token_endpoint"], data={"grant_type": "authorization_code", "client_id": settings.keycloak_client_id, "client_secret": settings.keycloak_client_secret, "redirect_uri": settings.keycloak_redirect_uri, "code": code, "code_verifier": verifier})
    if response.status_code != 200:
        raise HTTPException(401, "Identity provider rejected the authorization code")
    tokens = response.json()
    try:
        signing_key = jwt.PyJWKClient(document["jwks_uri"]).get_signing_key_from_jwt(tokens["id_token"])
        claims = jwt.decode(tokens["id_token"], signing_key.key, algorithms=["RS256", "ES256"], audience=settings.keycloak_client_id, issuer=_issuer(), options={"require": ["exp", "iat", "sub", "iss", "aud"]})
        if claims.get("nonce") != nonce:
            raise jwt.InvalidTokenError("nonce mismatch")
        return claims, str(tokens["refresh_token"]), int(tokens.get("refresh_expires_in", 1800))
    except (KeyError, jwt.PyJWTError) as exc:
        raise HTTPException(401, "Invalid identity token") from exc


def _keycloak_session_key(application_refresh_token: str) -> str:
    digest = hashlib.sha256(application_refresh_token.encode("ascii")).hexdigest()
    return f"breero:oidc-session:{digest}"


async def store_keycloak_session(
    application_refresh_token: str, keycloak_refresh_token: str, ttl_seconds: int
) -> None:
    client = redis.from_url(settings.redis_url, socket_timeout=2)
    try:
        await client.setex(
            _keycloak_session_key(application_refresh_token),
            max(60, ttl_seconds),
            keycloak_refresh_token,
        )
    finally:
        await client.aclose()


async def close_keycloak_session(application_refresh_token: str) -> None:
    client = redis.from_url(settings.redis_url, socket_timeout=2)
    try:
        raw = await client.getdel(_keycloak_session_key(application_refresh_token))
    finally:
        await client.aclose()
    if not raw:
        return
    document = await discovery()
    async with httpx.AsyncClient(timeout=10, follow_redirects=False) as http:
        response = await http.post(
            document["end_session_endpoint"],
            data={
                "client_id": settings.keycloak_client_id,
                "client_secret": settings.keycloak_client_secret,
                "refresh_token": raw.decode("ascii"),
            },
        )
    if response.status_code not in (200, 204):
        raise HTTPException(503, "Identity provider logout failed")


def roles_from_claims(claims: dict[str, Any]) -> set[str]:
    roles = set(claims.get("realm_access", {}).get("roles", []))
    for client in (settings.keycloak_audience, settings.keycloak_client_id):
        roles.update(claims.get("resource_access", {}).get(client, {}).get("roles", []))
    return roles


async def link_identity(session: AsyncSession, claims: dict[str, Any]) -> User:
    issuer, subject = str(claims["iss"]), str(claims["sub"])
    repository = UserRepository(session)
    user = await repository.by_keycloak_subject(issuer, subject)
    email = str(claims.get("email") or "").strip().lower()
    email_verified = claims.get("email_verified") is True
    if not user and email and email_verified:
        candidate = await repository.by_email(email)
        if candidate and not candidate.keycloak_subject:
            user = candidate
    mapped = next((ROLE_MAP[name] for name in ROLE_MAP if name in roles_from_claims(claims)), None)
    if mapped is None:
        raise HTTPException(403, "A Breero role is required")
    if not user:
        if not email or not email_verified:
            raise HTTPException(403, "A verified email is required")
        user = await repository.add(User(email=email, phone=None, full_name=str(claims.get("name") or claims.get("preferred_username") or email), password_hash=hash_password(secrets.token_urlsafe(48)), role=mapped, email_verified=bool(claims.get("email_verified"))))
    elif user.keycloak_subject and user.keycloak_subject != subject:
        raise HTTPException(409, "Identity is already linked")
    user.keycloak_subject = subject
    user.keycloak_issuer = issuer
    user.keycloak_username = str(claims.get("preferred_username") or "") or None
    user.keycloak_linked_at = user.keycloak_linked_at or datetime.now(UTC)
    user.role = mapped
    user.is_active = True
    if email:
        user.email = email
    if email_verified:
        user.email_verified = True
        user.email_verified_at = user.email_verified_at or datetime.now(UTC)
    await session.flush()
    return user
