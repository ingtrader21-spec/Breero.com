import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.domains.auth.dependencies import require_permissions
from app.domains.auth.models import User
from app.domains.dispatch.models import OfferStatus
from app.domains.jobs.models import JobStatus
from app.domains.provider_work.schemas import (
    ProviderJobList,
    ProviderOfferDecision,
    ProviderOfferList,
    ProviderOfferRead,
)
from app.domains.provider_work.service import ProviderWorkService

router = APIRouter()
jobs_read = require_permissions("provider.jobs.read")
offers_decide = require_permissions("provider.jobs.read", "provider.offers.decide")


@router.get("/jobs", response_model=ProviderJobList)
async def list_provider_jobs(
    user: Annotated[User, Depends(jobs_read)],
    session: Annotated[AsyncSession, Depends(get_db)],
    job_status: JobStatus | None = Query(default=None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> ProviderJobList:
    return await ProviderWorkService(session).list_jobs(
        user, status=job_status, limit=limit, offset=offset
    )


@router.get("/offers", response_model=ProviderOfferList)
async def list_provider_offers(
    user: Annotated[User, Depends(jobs_read)],
    session: Annotated[AsyncSession, Depends(get_db)],
    offer_status: OfferStatus | None = Query(default=None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> ProviderOfferList:
    return await ProviderWorkService(session).list_offers(
        user, status=offer_status, limit=limit, offset=offset
    )


@router.post("/offers/{offer_id}/decision", response_model=ProviderOfferRead)
async def decide_provider_offer(
    offer_id: uuid.UUID,
    decision: ProviderOfferDecision,
    user: Annotated[User, Depends(offers_decide)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProviderOfferRead:
    return await ProviderWorkService(session).decide_offer(offer_id, user, decision)
