import hmac
import secrets

from fastapi import Request, Response

from app.config import settings
from app.domains.auth.schemas import TokenResponse
from app.domains.auth.security import REFRESH_TOKEN_TTL_SECONDS, TOKEN_TTL_SECONDS

ACCESS_COOKIE = "breero_access"
REFRESH_COOKIE = "breero_refresh"
CSRF_COOKIE = "breero_csrf"


def set_browser_session(response: Response, session: TokenResponse) -> None:
    set_browser_tokens(
        response,
        session.access_token,
        session.refresh_token,
        session.expires_in,
        session.refresh_expires_in,
    )


def set_browser_tokens(
    response: Response,
    access_token: str,
    refresh_token: str,
    access_expires: int = TOKEN_TTL_SECONDS,
    refresh_expires: int = REFRESH_TOKEN_TTL_SECONDS,
) -> None:
    secure = settings.app_env.lower() == "production"
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        httponly=True,
        max_age=access_expires,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        httponly=True,
        max_age=refresh_expires,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        secrets.token_urlsafe(32),
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_browser_session(response: Response) -> None:
    secure = settings.app_env.lower() == "production"
    for name in (ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, path="/", secure=secure, samesite="lax")


def validate_csrf(request: Request) -> None:
    cookie = request.cookies.get(CSRF_COOKIE, "")
    header = request.headers.get("X-CSRF-Token", "")
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="CSRF validation failed")
