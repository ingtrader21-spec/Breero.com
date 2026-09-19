from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.core.rate_limit import (
    enforce_rate_limit as enforce_shared_rate_limit,
)
from app.core.rate_limit import (
    source_for_request,
)
from app.db.session import get_db
from app.domains.public_submissions.models import SubmissionType
from app.domains.public_submissions.schemas import (
    ContactCreate,
    ProviderInterestCreate,
    ServiceRequestCreate,
    SubmissionAccepted,
)
from app.domains.public_submissions.service import PublicSubmissionService

router = APIRouter()


async def enforce_rate_limit(request: Request) -> str:
    try:
        await enforce_shared_rate_limit(request, "public-form", 10, 60)
    except HTTPException as exc:
        if exc.status_code == 429:
            raise DomainError(
                "RATE_LIMITED",
                "Too many submissions; try again shortly",
                429,
                headers=exc.headers,
            ) from exc
        raise
    return source_for_request(request)


def validate_channel_contract(data) -> None:
    if (data.transactional_sms_consent or data.marketing_sms_consent) and not getattr(data, "phone", None):
        raise DomainError("PHONE_REQUIRED_FOR_SMS_CONSENT", "A phone number is required for SMS consent", 422)
    if getattr(data, "contact_preference", None) == "text" and not data.transactional_sms_consent:
        raise DomainError("SMS_CONSENT_REQUIRED", "Text contact requires transactional SMS consent", 422)


async def accept(data, submission_type, key, source, session):
    validate_channel_contract(data)
    if not key or len(key) > 255:
        raise DomainError(
            "IDEMPOTENCY_KEY_REQUIRED",
            "A valid Idempotency-Key is required",
            400,
        )
    return await PublicSubmissionService(session).accept(
        submission_type,
        data,
        key,
        source,
    )


@router.post(
    "/service-requests",
    response_model=SubmissionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def service_request(
    data: ServiceRequestCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    source: Annotated[str, Depends(enforce_rate_limit)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await accept(
        data,
        SubmissionType.SERVICE_REQUEST,
        idempotency_key,
        source,
        session,
    )


@router.post(
    "/contact",
    response_model=SubmissionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def contact(
    data: ContactCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    source: Annotated[str, Depends(enforce_rate_limit)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await accept(
        data,
        SubmissionType.CONTACT,
        idempotency_key,
        source,
        session,
    )


@router.post(
    "/provider-interest",
    response_model=SubmissionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def provider_interest(
    data: ProviderInterestCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    source: Annotated[str, Depends(enforce_rate_limit)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await accept(
        data,
        SubmissionType.PROVIDER_INTEREST,
        idempotency_key,
        source,
        session,
    )
