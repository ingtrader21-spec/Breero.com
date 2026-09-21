import uuid
from datetime import UTC, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import rate_limit
from app.core.responses import ApiResponse
from app.db.session import get_db
from app.domains.auth.browser_session import set_browser_tokens
from app.domains.auth.dependencies import optional_current_user
from app.domains.auth.models import User
from app.domains.booking.hold_service import CapacityHoldService
from app.domains.booking.public_schemas import (
    BookingRequestCreate,
    BookingRequestRead,
    CapacityHoldCreate,
    CapacityHoldRead,
    PublicAddressInput,
    PublicAvailabilityRequest,
    PublicAvailabilityResponse,
)
from app.domains.booking.public_service import BookingRequestService, PublicAvailabilityService
from app.domains.booking.schemas import AddressValidateRequest, AddressValidationResponse
from app.domains.booking.service import AddressService

router = APIRouter()


@router.post("/address/validate", response_model=ApiResponse[AddressValidationResponse])
async def validate_address(
    data: PublicAddressInput,
    session: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(rate_limit("booking-address", 30, 60))],
) -> ApiResponse[AddressValidationResponse]:
    result = await AddressService(session).validate(
        AddressValidateRequest(address=data.single_line())
    )
    return ApiResponse(data=result)


@router.post("/service-area/check", response_model=ApiResponse[AddressValidationResponse])
async def check_service_area(
    data: PublicAddressInput,
    session: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(rate_limit("booking-service-area", 30, 60))],
) -> ApiResponse[AddressValidationResponse]:
    return await validate_address(data, session, None)


@router.post("/timezone/resolve", response_model=ApiResponse[dict])
async def resolve_timezone(
    data: PublicAddressInput,
    session: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(rate_limit("booking-timezone", 30, 60))],
) -> ApiResponse[dict]:
    validated = await AddressService(session).validate(
        AddressValidateRequest(address=data.single_line())
    )
    if not validated.address_id:
        return ApiResponse(data={"timezone": None, "serviceable": False})
    from app.domains.booking.models import Address

    address = await session.get(Address, validated.address_id)
    return ApiResponse(
        data={
            "timezone": address.timezone_name if address else None,
            "serviceable": validated.serviceable,
            "address_id": str(validated.address_id),
        }
    )


@router.post("/availability", response_model=ApiResponse[PublicAvailabilityResponse])
async def availability(
    data: PublicAvailabilityRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(rate_limit("booking-availability", 20, 60))],
) -> ApiResponse[PublicAvailabilityResponse]:
    return ApiResponse(data=await PublicAvailabilityService(session).search(data))


def hold_read(hold) -> CapacityHoldRead:
    zone = ZoneInfo(hold.timezone_id)
    now = datetime.now(UTC)
    return CapacityHoldRead(
        hold_id=hold.id,
        status=hold.status.value,
        expires_at=hold.expires_at,
        expires_in_seconds=max(int((hold.expires_at - now).total_seconds()), 0),
        timezone=hold.timezone_id,
        start_local=hold.slot_start_utc.astimezone(zone).replace(tzinfo=None),
        end_local=hold.slot_end_utc.astimezone(zone).replace(tzinfo=None),
    )


@router.post("/holds", response_model=ApiResponse[CapacityHoldRead], status_code=201)
async def create_hold(
    data: CapacityHoldCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    booking_session: Annotated[str, Header(alias="X-Booking-Session")],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=128)],
    _: Annotated[None, Depends(rate_limit("booking-holds", 10, 300))],
) -> ApiResponse[CapacityHoldRead]:
    hold = await CapacityHoldService(session).create(
        data.service_id,
        data.address_id,
        data.start_local,
        data.timezone,
        booking_session,
        idempotency_key,
        emergency=data.emergency,
    )
    return ApiResponse(data=hold_read(hold))


@router.get("/holds/{hold_id}", response_model=ApiResponse[CapacityHoldRead])
async def get_hold(
    hold_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    booking_session: Annotated[str, Header(alias="X-Booking-Session")],
) -> ApiResponse[CapacityHoldRead]:
    return ApiResponse(
        data=hold_read(await CapacityHoldService(session).get(hold_id, booking_session))
    )


@router.delete("/holds/{hold_id}", status_code=status.HTTP_204_NO_CONTENT)
async def release_hold(
    hold_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    booking_session: Annotated[str, Header(alias="X-Booking-Session")],
) -> None:
    await CapacityHoldService(session).release(hold_id, booking_session)


@router.post("/requests", response_model=ApiResponse[BookingRequestRead], status_code=201)
async def create_request(
    data: BookingRequestCreate,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User | None, Depends(optional_current_user)],
    _: Annotated[None, Depends(rate_limit("booking-requests", 5, 300))],
) -> ApiResponse[BookingRequestRead]:
    result = await BookingRequestService(session).create(data, user)
    if result.access_token and result.refresh_token:
        set_browser_tokens(response, result.access_token, result.refresh_token)
        result = result.model_copy(update={"access_token": None, "refresh_token": None})
    return ApiResponse(data=result)


@router.get("/requests/{public_reference}", response_model=ApiResponse[dict])
async def request_status(
    public_reference: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    _rate_limit: Annotated[None, Depends(rate_limit("booking-request-status", 30, 60))],
) -> ApiResponse[dict]:
    _ = request
    return ApiResponse(data=await BookingRequestService(session).public_status(public_reference))
