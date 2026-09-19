import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.domains.auth.dependencies import require_roles
from app.domains.auth.models import User, UserRole
from app.domains.booking.scheduling import OperatorSchedulingService
from app.domains.booking.schemas import OperatorBookingConfirmation

router = APIRouter()


@router.post("/bookings/{booking_id}/confirm", status_code=status.HTTP_201_CREATED)
async def confirm_booking(
    booking_id: uuid.UUID,
    payload: OperatorBookingConfirmation,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.operations, UserRole.admin)),
):
    return await OperatorSchedulingService(session).confirm(
        booking_id,
        payload.worker_id,
        user.id,
        payload.reason,
    )
