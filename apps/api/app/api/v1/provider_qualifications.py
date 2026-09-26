import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.provider_http import correlation_id, require_if_match, set_etag
from app.db.session import get_db
from app.domains.auth.dependencies import require_permissions
from app.domains.auth.models import User
from app.domains.provider_qualifications.schemas import (
    QualificationCreate,
    QualificationList,
    QualificationRead,
    QualificationReviewDecision,
    QualificationUpdate,
)
from app.domains.provider_qualifications.service import ProviderQualificationService

router = APIRouter()
admin_router = APIRouter()
qualification_read = require_permissions("provider.credentials.read")
qualification_manage = require_permissions("provider.qualifications.manage")
qualification_review = require_permissions("trust.credentials.manage")


@router.get("", response_model=QualificationList)
async def list_provider_qualifications(
    user: Annotated[User, Depends(qualification_read)],
    session: Annotated[AsyncSession, Depends(get_db)],
    worker_id: uuid.UUID | None = Query(default=None),
    include_withdrawn: bool = Query(default=False),
) -> QualificationList:
    return await ProviderQualificationService(session).list_qualifications(
        user, worker_id=worker_id, include_withdrawn=include_withdrawn
    )


@router.post(
    "",
    response_model=QualificationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_provider_qualification(
    command: QualificationCreate,
    request: Request,
    response: Response,
    user: Annotated[User, Depends(qualification_manage)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> QualificationRead:
    result = await ProviderQualificationService(session).create(
        user, command, correlation_id=correlation_id(request)
    )
    set_etag(response, result.version)
    return result


@router.get("/{qualification_id}", response_model=QualificationRead)
async def get_provider_qualification(
    qualification_id: uuid.UUID,
    response: Response,
    user: Annotated[User, Depends(qualification_read)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> QualificationRead:
    result = await ProviderQualificationService(session).get(qualification_id, user)
    set_etag(response, result.version)
    return result


@router.patch("/{qualification_id}", response_model=QualificationRead)
async def update_provider_qualification(
    qualification_id: uuid.UUID,
    command: QualificationUpdate,
    request: Request,
    response: Response,
    user: Annotated[User, Depends(qualification_manage)],
    session: Annotated[AsyncSession, Depends(get_db)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> QualificationRead:
    result = await ProviderQualificationService(session).update(
        qualification_id,
        user,
        command,
        expected_version=require_if_match(if_match),
        correlation_id=correlation_id(request),
    )
    set_etag(response, result.version)
    return result


@router.post("/{qualification_id}/submit", response_model=QualificationRead)
async def submit_provider_qualification(
    qualification_id: uuid.UUID,
    request: Request,
    response: Response,
    user: Annotated[User, Depends(qualification_manage)],
    session: Annotated[AsyncSession, Depends(get_db)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> QualificationRead:
    result = await ProviderQualificationService(session).submit(
        qualification_id,
        user,
        expected_version=require_if_match(if_match),
        correlation_id=correlation_id(request),
    )
    set_etag(response, result.version)
    return result


@router.delete("/{qualification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def withdraw_provider_qualification(
    qualification_id: uuid.UUID,
    request: Request,
    user: Annotated[User, Depends(qualification_manage)],
    session: Annotated[AsyncSession, Depends(get_db)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> None:
    await ProviderQualificationService(session).withdraw(
        qualification_id,
        user,
        expected_version=require_if_match(if_match),
        correlation_id=correlation_id(request),
    )


@router.post(
    "/{qualification_id}/evidence",
    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    responses={503: {"description": "Governed document storage is not configured."}},
)
async def upload_provider_qualification_evidence(
    qualification_id: uuid.UUID,
    user: Annotated[User, Depends(qualification_manage)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Fail closed. The request body is never read or persisted."""

    await ProviderQualificationService(session).reject_evidence_upload(qualification_id, user)


@admin_router.post("/{qualification_id}/review", response_model=QualificationRead)
async def review_provider_qualification(
    qualification_id: uuid.UUID,
    decision: QualificationReviewDecision,
    request: Request,
    actor: Annotated[User, Depends(qualification_review)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> QualificationRead:
    return await ProviderQualificationService(session).review(
        qualification_id, actor, decision, correlation_id=correlation_id(request)
    )
