from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.domains.auth.browser_session import (
    ACCESS_COOKIE,
    CSRF_COOKIE,
    REFRESH_COOKIE,
    clear_browser_session,
    set_browser_session,
    validate_csrf,
)
from app.domains.auth.dependencies import current_user
from app.domains.auth.keycloak import (
    OIDC_COOKIE,
    authorization_url,
    close_keycloak_session,
    exchange_code,
    link_identity,
    read_transaction,
    store_keycloak_session,
)
from app.domains.auth.models import User
from app.domains.auth.schemas import (
    BrowserSessionResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    ProviderRegisterRequest,
    ProviderRegistrationResponse,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SetPasswordRequest,
    TokenRequest,
    TokenResponse,
    UserRead,
)
from app.domains.auth.service import AuthService

router = APIRouter()


def client(request: Request) -> tuple[str | None, str | None]:
    return request.headers.get("user-agent"), request.client.host if request.client else None


def local_auth_only() -> None:
    if settings.keycloak_enabled or not settings.breero_local_password_auth:
        raise HTTPException(403, "Password authentication is managed by the identity provider")


@router.get("/csrf")
async def browser_csrf_token(request: Request, response: Response) -> dict[str, str]:
    """Expose only the double-submit token to approved frontend origins."""
    origin = request.headers.get("origin")
    own_origin = f"{request.url.scheme}://{request.url.netloc}"
    if origin and origin != own_origin and origin not in settings.allowed_origins:
        raise HTTPException(403, "Frontend origin is not allowed")
    token = request.cookies.get(CSRF_COOKIE)
    if not token or not (request.cookies.get(ACCESS_COOKIE) or request.cookies.get(REFRESH_COOKIE)):
        raise HTTPException(401, "Browser session required")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Vary"] = "Origin, Cookie"
    return {"csrf_token": token}


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    data: RegisterRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(rate_limit("register", 5, 60))],
) -> TokenResponse:
    if settings.keycloak_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public account registration is disabled",
        )
    return await AuthService(session).register(data, *client(request))


@router.post("/register/client", response_model=TokenResponse, status_code=201)
async def register_client(
    data: RegisterRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(rate_limit("register-client", 5, 60))],
) -> TokenResponse:
    if settings.keycloak_enabled:
        raise HTTPException(status_code=403, detail="Public account registration is disabled")
    return await AuthService(session).register(data, *client(request))


@router.post("/register/provider", response_model=ProviderRegistrationResponse, status_code=201)
async def register_provider(
    data: ProviderRegisterRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(rate_limit("register-provider", 3, 300))],
) -> ProviderRegistrationResponse:
    if settings.keycloak_enabled:
        raise HTTPException(status_code=403, detail="Public provider registration is disabled")
    token, vendor = await AuthService(session).register_provider(data, *client(request))
    return ProviderRegistrationResponse(
        **token.model_dump(),
        provider_organization_id=vendor.id,
        onboarding_status=vendor.onboarding_status,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(rate_limit("login", 10, 60))],
) -> TokenResponse:
    local_auth_only()
    return await AuthService(session).login(data, *client(request))


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    data: RefreshRequest, request: Request, session: Annotated[AsyncSession, Depends(get_db)]
) -> TokenResponse:
    return await AuthService(session).refresh(data.refresh_token, *client(request))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(data: RefreshRequest, session: Annotated[AsyncSession, Depends(get_db)]) -> None:
    await AuthService(session).logout(data.refresh_token)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    user: Annotated[User, Depends(current_user)], session: Annotated[AsyncSession, Depends(get_db)]
) -> None:
    await AuthService(session).logout_all(user)


@router.post("/password/forgot", response_model=MessageResponse)
async def forgot(
    data: ForgotPasswordRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(rate_limit("password-forgot", 5, 300))],
) -> MessageResponse:
    local_auth_only()
    await AuthService(session).forgot_password(str(data.email))
    return MessageResponse(message="If the account exists, reset instructions have been sent")


@router.post("/password/reset", response_model=MessageResponse)
async def reset(
    data: ResetPasswordRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(rate_limit("password-reset", 10, 300))],
) -> MessageResponse:
    local_auth_only()
    await AuthService(session).reset_password(data.token, data.new_password)
    return MessageResponse(message="Password reset")


@router.post("/password/change", response_model=MessageResponse)
async def change(
    data: ChangePasswordRequest,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    local_auth_only()
    await AuthService(session).change_password(user, data.current_password, data.new_password)
    return MessageResponse(message="Password changed; active sessions revoked")


@router.post("/password/set", response_model=MessageResponse)
async def set_password(
    data: SetPasswordRequest,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    local_auth_only()
    await AuthService(session).set_initial_password(user, data.new_password)
    return MessageResponse(message="Password set; active sessions revoked")


@router.post("/browser/password/set", response_model=BrowserSessionResponse)
async def browser_set_password(
    data: SetPasswordRequest,
    request: Request,
    response: Response,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> BrowserSessionResponse:
    local_auth_only()
    """Complete an auto-created account without leaving a revoked browser session."""
    service = AuthService(session)
    await service.set_initial_password(user, data.new_password)
    tokens = await service.login(LoginRequest(email=user.email, password=data.new_password), *client(request))
    set_browser_session(response, tokens)
    return BrowserSessionResponse(user=tokens.user)


@router.post("/email/verify", response_model=MessageResponse)
async def verify(
    data: TokenRequest, session: Annotated[AsyncSession, Depends(get_db)]
) -> MessageResponse:
    await AuthService(session).verify_email(data.token)
    return MessageResponse(message="Email verified")


@router.post("/email/resend-verification", response_model=MessageResponse)
async def resend(
    user: Annotated[User, Depends(current_user)], session: Annotated[AsyncSession, Depends(get_db)]
) -> MessageResponse:
    await AuthService(session).resend_verification(user)
    return MessageResponse(message="Verification sent if required")


@router.post("/email/resend", response_model=MessageResponse)
async def resend_alias(
    user: Annotated[User, Depends(current_user)], session: Annotated[AsyncSession, Depends(get_db)]
) -> MessageResponse:
    return await resend(user, session)


@router.post("/phone/verify", response_model=MessageResponse)
async def verify_phone(
    data: TokenRequest,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    await AuthService(session).verify_phone(user, data.token)
    return MessageResponse(message="Phone verified")


@router.get("/me", response_model=UserRead)
async def me(user: Annotated[User, Depends(current_user)]) -> User:
    return user


@router.post("/browser/login", response_model=BrowserSessionResponse)
async def browser_login(
    data: LoginRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(rate_limit("browser-login", 10, 60))],
) -> BrowserSessionResponse:
    local_auth_only()
    tokens = await AuthService(session).login(data, *client(request))
    set_browser_session(response, tokens)
    return BrowserSessionResponse(user=tokens.user)


@router.post("/browser/register/client", response_model=BrowserSessionResponse, status_code=201)
async def browser_register_client(
    data: RegisterRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(rate_limit("browser-register-client", 5, 60))],
) -> BrowserSessionResponse:
    if settings.keycloak_enabled:
        raise HTTPException(status_code=403, detail="Public account registration is disabled")
    tokens = await AuthService(session).register(data, *client(request))
    set_browser_session(response, tokens)
    return BrowserSessionResponse(user=tokens.user)


@router.post("/browser/register/provider", response_model=BrowserSessionResponse, status_code=201)
async def browser_register_provider(
    data: ProviderRegisterRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(rate_limit("browser-register-provider", 3, 300))],
) -> BrowserSessionResponse:
    if settings.keycloak_enabled:
        raise HTTPException(status_code=403, detail="Public provider registration is disabled")
    tokens, _vendor = await AuthService(session).register_provider(data, *client(request))
    set_browser_session(response, tokens)
    return BrowserSessionResponse(user=tokens.user)


@router.post("/browser/refresh", response_model=BrowserSessionResponse)
async def browser_refresh(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> BrowserSessionResponse:
    validate_csrf(request)
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Authentication required")
    tokens = await AuthService(session).refresh(refresh_token, *client(request))
    set_browser_session(response, tokens)
    return BrowserSessionResponse(user=tokens.user)


@router.post("/browser/logout", status_code=status.HTTP_204_NO_CONTENT)
async def browser_logout(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    validate_csrf(request)
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if refresh_token:
        await AuthService(session).logout(refresh_token)
    clear_browser_session(response)


@router.get("/keycloak/login", response_class=RedirectResponse)
async def keycloak_login(return_to: str = Query(default="/account")) -> RedirectResponse:
    if not settings.keycloak_enabled:
        raise HTTPException(404, "Identity provider login is disabled")
    url, transaction = await authorization_url(return_to)
    response = RedirectResponse(url, status_code=302)
    response.set_cookie(OIDC_COOKIE, transaction, httponly=True, secure=settings.app_env.lower() == "production", samesite="lax", max_age=600, path="/api/v1/auth/keycloak")
    return response


@router.get("/keycloak/callback", response_class=RedirectResponse)
async def keycloak_callback(
    request: Request,
    code: str,
    state: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RedirectResponse:
    if not settings.keycloak_enabled:
        raise HTTPException(404, "Identity provider login is disabled")
    transaction = read_transaction(request.cookies.get(OIDC_COOKIE), state)
    claims, keycloak_refresh_token, keycloak_refresh_ttl = await exchange_code(
        code, str(transaction["verifier"]), str(transaction["nonce"])
    )
    user = await link_identity(session, claims)
    tokens = await AuthService(session).application_session(user, *client(request))
    await store_keycloak_session(
        tokens.refresh_token, keycloak_refresh_token, keycloak_refresh_ttl
    )
    response = RedirectResponse(str(transaction["return_to"]), status_code=303)
    set_browser_session(response, tokens)
    response.delete_cookie(OIDC_COOKIE, path="/api/v1/auth/keycloak")
    return response


@router.post("/keycloak/logout")
async def keycloak_logout(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    validate_csrf(request)
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if refresh_token:
        await AuthService(session).logout(refresh_token)
        await close_keycloak_session(refresh_token)
    clear_browser_session(response)
    return {"end_session_url": settings.breero_web_url.rstrip("/")}


@router.get("/keycloak/status")
async def keycloak_status() -> dict[str, str | bool]:
    return {"enabled": settings.keycloak_enabled, "issuer": settings.keycloak_issuer if settings.keycloak_enabled else "", "local_password_auth": settings.breero_local_password_auth}
