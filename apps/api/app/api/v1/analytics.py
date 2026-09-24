from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal, get_db
from app.domains.analytics.schemas import MarketplaceMetricsRead
from app.domains.analytics.scope import resolve_marketplace_scope, resolve_provider_scope
from app.domains.analytics.service import MarketplaceMetricsService
from app.domains.auth.dependencies import current_user
from app.domains.auth.models import User

router = APIRouter()

WindowStart = Annotated[
    datetime | None,
    Query(description="Inclusive window start with timezone offset. Defaults to 30 days before end."),
]
WindowEnd = Annotated[
    datetime | None,
    Query(description="Exclusive window end with timezone offset. Defaults to now."),
]

ERROR_RESPONSES: dict[int | str, dict[str, str]] = {
    401: {"description": "Authentication required"},
    403: {"description": "Permission or tenant scope denied"},
    422: {"description": "Invalid analytics window"},
}


def metrics_service() -> MarketplaceMetricsService:
    return MarketplaceMetricsService(SessionLocal)


@router.get(
    "/marketplace/metrics",
    response_model=MarketplaceMetricsRead,
    responses=ERROR_RESPONSES,
    summary="Marketplace-wide metrics projection for internal analysts",
)
async def marketplace_metrics(
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[MarketplaceMetricsService, Depends(metrics_service)],
    start: WindowStart = None,
    end: WindowEnd = None,
) -> MarketplaceMetricsRead:
    scope = await resolve_marketplace_scope(session, user)
    return await service.metrics(scope, start, end)


@router.get(
    "/provider/metrics",
    response_model=MarketplaceMetricsRead,
    responses=ERROR_RESPONSES,
    summary="Metrics projection limited to the caller's provider organization",
)
async def provider_metrics(
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[MarketplaceMetricsService, Depends(metrics_service)],
    start: WindowStart = None,
    end: WindowEnd = None,
) -> MarketplaceMetricsRead:
    scope = await resolve_provider_scope(session, user)
    return await service.metrics(scope, start, end)
