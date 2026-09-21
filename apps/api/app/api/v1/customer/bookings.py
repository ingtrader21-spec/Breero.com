import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.customer.dependencies import customer_for, paginate
from app.api.v1.customer.schemas import (
    BookingRescheduleRequest,
    Page,
)
from app.db.session import get_db
from app.domains.auth.dependencies import current_user
from app.domains.auth.models import User
from app.domains.booking.capacity_models import BookingCapacityHold, CapacityHoldStatus
from app.domains.booking.hold_service import owner_fingerprint
from app.domains.booking.models import Booking, BookingStatus
from app.domains.booking.presenters import booking_to_response as to_response
from app.domains.booking.schemas import BookingResponse
from app.domains.common.outbox import AuditLog
from app.domains.jobs.models import Job, JobStatus
from app.domains.jobs.service import JobService

router = APIRouter()

@router.get("/bookings", response_model=Page)
async def bookings(
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Page:
    c = await customer_for(session, user)
    items, total = await paginate(
        session,
        select(Booking).where(Booking.customer_id == c.id).order_by(Booking.created_at.desc()),
        select(func.count()).select_from(Booking).where(Booking.customer_id == c.id),
        page,
        page_size,
    )
    return Page(
        items=[to_response(x).model_dump() for x in items],
        total=total,
        page=page,
        page_size=page_size,
    )

@router.get("/bookings/{booking_id}", response_model=BookingResponse)
async def booking(
    booking_id: uuid.UUID,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> BookingResponse:
    c = await customer_for(session, user)
    item = await session.scalar(
        select(Booking).where(Booking.id == booking_id, Booking.customer_id == c.id)
    )
    if not item:
        raise HTTPException(404, "Booking not found")
    return to_response(item)

@router.post("/bookings/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking(
    booking_id: uuid.UUID,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> BookingResponse:
    customer = await customer_for(session, user)
    item = await session.scalar(
        select(Booking)
        .where(Booking.id == booking_id, Booking.customer_id == customer.id)
        .with_for_update()
    )
    if not item:
        raise HTTPException(404, "Booking not found")
    if item.status == BookingStatus.CANCELLED:
        return to_response(item)
    if item.status not in {
        BookingStatus.REQUESTED,
        BookingStatus.PENDING_REVIEW,
        BookingStatus.CAPACITY_HELD,
        BookingStatus.AWAITING_ASSIGNMENT,
        BookingStatus.PENDING_MANUAL_DISPATCH,
        BookingStatus.PROVIDER_ASSIGNED,
        BookingStatus.PENDING_PAYMENT,
        BookingStatus.PENDING_PROVIDER_CONFIRMATION,
        BookingStatus.CONFIRMED,
    }:
        raise HTTPException(409, "Booking cannot be cancelled in its current state")
    job = await session.scalar(select(Job).where(Job.booking_id == item.id).with_for_update())
    if job and job.status not in {JobStatus.CREATED, JobStatus.MATCHING, JobStatus.OFFERED}:
        raise HTTPException(409, "Booking can no longer be cancelled online")
    previous = item.status.value
    item.status = BookingStatus.CANCELLED
    item.guest_confirmation_revoked_at = datetime.now(UTC)
    if job:
        JobService(session).apply_transition(
            job, JobStatus.CANCELLED, user.id, "customer", "customer_cancelled_booking"
        )
    await session.execute(
        update(BookingCapacityHold)
        .where(
            BookingCapacityHold.booking_id == item.id,
            BookingCapacityHold.status == CapacityHoldStatus.HELD,
        )
        .values(status=CapacityHoldStatus.RELEASED, released_at=datetime.now(UTC))
    )
    session.add(
        AuditLog(
            actor_id=user.id,
            actor_type="customer",
            action="booking.cancel",
            resource_type="booking",
            resource_id=item.id,
            metadata_json={"from_status": previous, "refund_automatic": False},
            created_at=datetime.now(UTC),
        )
    )
    await session.commit()
    return to_response(item)

@router.post("/bookings/{booking_id}/reschedule", response_model=BookingResponse)
async def reschedule_booking(
    booking_id: uuid.UUID,
    data: BookingRescheduleRequest,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> BookingResponse:
    customer = await customer_for(session, user)
    item = await session.scalar(
        select(Booking)
        .where(Booking.id == booking_id, Booking.customer_id == customer.id)
        .with_for_update()
    )
    if not item:
        raise HTTPException(404, "Booking not found")
    if item.status not in {
        BookingStatus.REQUESTED,
        BookingStatus.PENDING_MANUAL_DISPATCH,
        BookingStatus.PROVIDER_ASSIGNED,
        BookingStatus.CONFIRMED,
    }:
        raise HTTPException(409, "Booking cannot be rescheduled in its current state")
    hold = await session.scalar(
        select(BookingCapacityHold)
        .where(BookingCapacityHold.id == data.hold_id)
        .with_for_update()
    )
    now = datetime.now(UTC)
    if (
        not hold
        or hold.owner_fingerprint_hash != owner_fingerprint(data.booking_session)
        or hold.status != CapacityHoldStatus.HELD
        or hold.expires_at <= now
        or hold.service_id != item.service_id
        or hold.address_id != item.address_id
    ):
        raise HTTPException(409, "A valid hold for this booking is required")
    await session.execute(
        update(BookingCapacityHold)
        .where(
            BookingCapacityHold.booking_id == item.id,
            BookingCapacityHold.id != hold.id,
            BookingCapacityHold.status == CapacityHoldStatus.HELD,
        )
        .values(status=CapacityHoldStatus.RELEASED, released_at=now)
    )
    previous = {"start": item.window_start.isoformat(), "end": item.window_end.isoformat()}
    item.window_start = hold.slot_start_utc
    item.window_end = hold.slot_end_utc
    item.service_timezone_id = hold.timezone_id
    item.provider_worker_id = None
    item.status = BookingStatus.PENDING_MANUAL_DISPATCH
    hold.booking_id = item.id
    hold.status = CapacityHoldStatus.CONVERTED
    hold.converted_at = now
    session.add(
        AuditLog(
            actor_id=user.id,
            actor_type="customer",
            action="booking.rescheduled",
            resource_type="booking",
            resource_id=item.id,
            metadata_json={
                "previous": previous,
                "new_start": item.window_start.isoformat(),
                "timezone_id": item.service_timezone_id,
            },
            created_at=now,
        )
    )
    await session.commit()
    return to_response(item)
