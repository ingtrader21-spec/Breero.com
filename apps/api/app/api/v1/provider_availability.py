import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.provider_http import correlation_id, require_if_match, set_etag
from app.db.session import get_db
from app.domains.auth.dependencies import require_permissions
from app.domains.auth.models import User
from app.domains.provider_availability.schemas import (
    AvailabilityPreviewRead,
    AvailabilityRuleCreate,
    AvailabilityRuleRead,
    AvailabilityRuleUpdate,
    BlackoutPeriodCreate,
    BlackoutPeriodRead,
    BlackoutPeriodUpdate,
    ProviderAvailabilityRead,
)
from app.domains.provider_availability.service import ProviderAvailabilityService

router = APIRouter()
availability_read = require_permissions("provider.availability.read")
availability_manage = require_permissions("provider.availability.manage")


@router.get("", response_model=ProviderAvailabilityRead)
async def get_provider_availability(
    user: Annotated[User, Depends(availability_read)],
    session: Annotated[AsyncSession, Depends(get_db)],
    worker_id: uuid.UUID | None = Query(default=None),
) -> ProviderAvailabilityRead:
    return await ProviderAvailabilityService(session).snapshot(user, worker_id=worker_id)


@router.get("/preview", response_model=AvailabilityPreviewRead)
async def preview_provider_availability(
    user: Annotated[User, Depends(availability_read)],
    session: Annotated[AsyncSession, Depends(get_db)],
    starts_at: datetime = Query(description="Inclusive UTC-offset start of the window"),
    ends_at: datetime = Query(description="Exclusive UTC-offset end; at most 31 days"),
    worker_id: uuid.UUID | None = Query(default=None),
) -> AvailabilityPreviewRead:
    return await ProviderAvailabilityService(session).preview(
        user, starts_at=starts_at, ends_at=ends_at, worker_id=worker_id
    )


@router.post(
    "/rules",
    response_model=AvailabilityRuleRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_provider_availability_rule(
    command: AvailabilityRuleCreate,
    request: Request,
    response: Response,
    user: Annotated[User, Depends(availability_manage)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AvailabilityRuleRead:
    result = await ProviderAvailabilityService(session).create_rule(
        user, command, correlation_id=correlation_id(request)
    )
    set_etag(response, result.version)
    return result


@router.patch("/rules/{rule_id}", response_model=AvailabilityRuleRead)
async def update_provider_availability_rule(
    rule_id: uuid.UUID,
    command: AvailabilityRuleUpdate,
    request: Request,
    response: Response,
    user: Annotated[User, Depends(availability_manage)],
    session: Annotated[AsyncSession, Depends(get_db)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> AvailabilityRuleRead:
    result = await ProviderAvailabilityService(session).update_rule(
        rule_id,
        user,
        command,
        expected_version=require_if_match(if_match),
        correlation_id=correlation_id(request),
    )
    set_etag(response, result.version)
    return result


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider_availability_rule(
    rule_id: uuid.UUID,
    request: Request,
    user: Annotated[User, Depends(availability_manage)],
    session: Annotated[AsyncSession, Depends(get_db)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> None:
    await ProviderAvailabilityService(session).delete_rule(
        rule_id,
        user,
        expected_version=require_if_match(if_match),
        correlation_id=correlation_id(request),
    )


@router.post(
    "/blackouts",
    response_model=BlackoutPeriodRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_provider_blackout_period(
    command: BlackoutPeriodCreate,
    request: Request,
    response: Response,
    user: Annotated[User, Depends(availability_manage)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> BlackoutPeriodRead:
    result = await ProviderAvailabilityService(session).create_blackout(
        user, command, correlation_id=correlation_id(request)
    )
    set_etag(response, result.version)
    return result


@router.patch("/blackouts/{blackout_id}", response_model=BlackoutPeriodRead)
async def update_provider_blackout_period(
    blackout_id: uuid.UUID,
    command: BlackoutPeriodUpdate,
    request: Request,
    response: Response,
    user: Annotated[User, Depends(availability_manage)],
    session: Annotated[AsyncSession, Depends(get_db)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> BlackoutPeriodRead:
    result = await ProviderAvailabilityService(session).update_blackout(
        blackout_id,
        user,
        command,
        expected_version=require_if_match(if_match),
        correlation_id=correlation_id(request),
    )
    set_etag(response, result.version)
    return result


@router.delete("/blackouts/{blackout_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider_blackout_period(
    blackout_id: uuid.UUID,
    request: Request,
    user: Annotated[User, Depends(availability_manage)],
    session: Annotated[AsyncSession, Depends(get_db)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> None:
    await ProviderAvailabilityService(session).delete_blackout(
        blackout_id,
        user,
        expected_version=require_if_match(if_match),
        correlation_id=correlation_id(request),
    )
