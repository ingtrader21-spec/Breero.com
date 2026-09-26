import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.provider_http import optional_if_match, set_etag
from app.config import settings
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.domains.auth.dependencies import require_permissions
from app.domains.auth.models import User
from app.domains.workforce.models import ProviderApplicationStatus
from app.domains.workforce.onboarding_service import (
    ProviderOnboardingService,
    ProviderRegistrationService,
)
from app.domains.workforce.schemas import (
    ProviderApplicationDecision,
    ProviderApplicationList,
    ProviderApplicationRead,
    ProviderOnboardingChecklist,
    ProviderOnboardingUpdate,
    ProviderProfileUpdate,
    ProviderRegisterRequest,
    ProviderRegistrationResponse,
    VendorRead,
)

registration_router = APIRouter()
provider_router = APIRouter()
admin_router = APIRouter()
provider_read = require_permissions("provider.profile.read")
provider_write = require_permissions("provider.profile.write")
provider_review = require_permissions("admin.access.manage")


@registration_router.post(
    "/register/provider",
    response_model=ProviderRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_provider(
    data: ProviderRegisterRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(rate_limit("provider-register", 5, 300))],
) -> ProviderRegistrationResponse:
    if not settings.provider_self_service_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Provider self-service registration is not enabled",
        )
    if settings.keycloak_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Provider registration is delegated to the configured identity provider",
        )
    user_agent = request.headers.get("user-agent")
    ip = request.client.host if request.client else None
    return await ProviderRegistrationService(session).register(
        data,
        user_agent=user_agent,
        ip=ip,
    )


@provider_router.get("/profile", response_model=VendorRead)
async def provider_profile(
    user: Annotated[User, Depends(provider_read)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> VendorRead:
    vendor = await ProviderOnboardingService(session).profile(user)
    return VendorRead.model_validate(vendor)


@provider_router.patch("/profile", response_model=VendorRead)
async def update_provider_profile(
    data: ProviderProfileUpdate,
    user: Annotated[User, Depends(provider_write)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> VendorRead:
    vendor = await ProviderOnboardingService(session).update_profile(user, data)
    return VendorRead.model_validate(vendor)


@provider_router.get("/onboarding", response_model=ProviderApplicationRead)
async def provider_onboarding(
    response: Response,
    user: Annotated[User, Depends(provider_read)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProviderApplicationRead:
    application = await ProviderOnboardingService(session).onboarding(user)
    set_etag(response, application.version)
    return ProviderApplicationRead.model_validate(application)


@provider_router.get(
    "/onboarding/checklist",
    response_model=ProviderOnboardingChecklist,
)
async def provider_onboarding_checklist(
    user: Annotated[User, Depends(provider_read)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProviderOnboardingChecklist:
    return await ProviderOnboardingService(session).checklist(user)


@provider_router.patch("/onboarding", response_model=ProviderApplicationRead)
async def update_provider_onboarding(
    data: ProviderOnboardingUpdate,
    response: Response,
    user: Annotated[User, Depends(provider_write)],
    session: Annotated[AsyncSession, Depends(get_db)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> ProviderApplicationRead:
    application = await ProviderOnboardingService(session).update_onboarding(
        user,
        data,
        expected_version=optional_if_match(if_match),
    )
    set_etag(response, application.version)
    return ProviderApplicationRead.model_validate(application)


@provider_router.post("/onboarding/submit", response_model=ProviderApplicationRead)
async def submit_provider_onboarding(
    response: Response,
    user: Annotated[User, Depends(provider_write)],
    session: Annotated[AsyncSession, Depends(get_db)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> ProviderApplicationRead:
    application = await ProviderOnboardingService(session).submit(
        user,
        expected_version=optional_if_match(if_match),
    )
    set_etag(response, application.version)
    return ProviderApplicationRead.model_validate(application)


@admin_router.get("", response_model=ProviderApplicationList)
async def list_provider_applications(
    _: Annotated[User, Depends(provider_review)],
    session: Annotated[AsyncSession, Depends(get_db)],
    application_status: ProviderApplicationStatus | None = Query(default=None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> ProviderApplicationList:
    return await ProviderOnboardingService(session).list_applications(
        status=application_status,
        limit=limit,
        offset=offset,
    )


@admin_router.get("/{application_id}", response_model=ProviderApplicationRead)
async def get_provider_application(
    application_id: uuid.UUID,
    _: Annotated[User, Depends(provider_review)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProviderApplicationRead:
    application = await ProviderOnboardingService(session).application(application_id)
    return ProviderApplicationRead.model_validate(application)


@admin_router.post("/{application_id}/approve", response_model=ProviderApplicationRead)
async def approve_provider_application(
    application_id: uuid.UUID,
    data: ProviderApplicationDecision,
    actor: Annotated[User, Depends(provider_review)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProviderApplicationRead:
    application = await ProviderOnboardingService(session).approve(application_id, actor, data)
    return ProviderApplicationRead.model_validate(application)


@admin_router.post("/{application_id}/reject", response_model=ProviderApplicationRead)
async def reject_provider_application(
    application_id: uuid.UUID,
    data: ProviderApplicationDecision,
    actor: Annotated[User, Depends(provider_review)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProviderApplicationRead:
    application = await ProviderOnboardingService(session).reject(application_id, actor, data)
    return ProviderApplicationRead.model_validate(application)


@admin_router.post(
    "/{application_id}/request-information",
    response_model=ProviderApplicationRead,
)
async def request_provider_information(
    application_id: uuid.UUID,
    data: ProviderApplicationDecision,
    actor: Annotated[User, Depends(provider_review)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProviderApplicationRead:
    application = await ProviderOnboardingService(session).request_information(
        application_id,
        actor,
        data,
    )
    return ProviderApplicationRead.model_validate(application)
