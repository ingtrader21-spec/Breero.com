import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.domains.auth.dependencies import require_roles
from app.domains.auth.models import User, UserRole
from app.domains.booking.models import Booking
from app.domains.booking.schemas import BookingResponse
from app.domains.dispatch.admin_schemas import (
    AdminAssignmentRequest,
    AdminUnassignmentRequest,
    CandidateRead,
)
from app.domains.dispatch.admin_service import AdminDispatchService

router = APIRouter()
dispatcher = require_roles(UserRole.operations, UserRole.admin)


@router.get("/bookings", response_model=list[BookingResponse])
async def bookings(
    session: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(dispatcher)],
):
    from app.api.v1.bookings import to_response

    records = list(
        (
            await session.scalars(
                select(Booking).order_by(Booking.window_start).limit(200)
            )
        ).all()
    )
    return [to_response(record) for record in records]


@router.get("/bookings/{booking_id}", response_model=BookingResponse)
async def booking(
    booking_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(dispatcher)],
):
    from app.api.v1.bookings import to_response
    from app.core.errors import DomainError

    record = await session.get(Booking, booking_id)
    if not record:
        raise DomainError("NOT_FOUND", "Booking not found", 404)
    return to_response(record)


@router.get("/bookings/{booking_id}/provider-candidates", response_model=list[CandidateRead])
async def candidates(
    booking_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(dispatcher)],
):
    return await AdminDispatchService(session).candidates(booking_id)


@router.post("/bookings/{booking_id}/assign", response_model=BookingResponse)
async def assign(
    booking_id: uuid.UUID,
    data: AdminAssignmentRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(dispatcher)],
):
    from app.api.v1.bookings import to_response

    return to_response(
        await AdminDispatchService(session).assign(
            booking_id, data.professional_id, user.id, data.reason
        )
    )


@router.post("/bookings/{booking_id}/reassign", response_model=BookingResponse)
async def reassign(
    booking_id: uuid.UUID,
    data: AdminAssignmentRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(dispatcher)],
):
    from app.api.v1.bookings import to_response

    return to_response(
        await AdminDispatchService(session).assign(
            booking_id, data.professional_id, user.id, data.reason, reassign=True
        )
    )


@router.post("/bookings/{booking_id}/unassign", response_model=BookingResponse)
async def unassign(
    booking_id: uuid.UUID,
    data: AdminUnassignmentRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(dispatcher)],
):
    from app.api.v1.bookings import to_response

    return to_response(
        await AdminDispatchService(session).unassign(booking_id, user.id, data.reason)
    )
