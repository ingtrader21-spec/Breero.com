import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.domains.auth.dependencies import require_roles
from app.domains.auth.models import User, UserRole
from app.domains.booking.models import ProviderServiceCoverage, ProviderWorkingHours
from app.domains.catalog.models import Service
from app.domains.workforce.repository import WorkforceRepository
from app.domains.workforce.schemas import BookingCoverageWrite, VendorRead, VendorStatusUpdate

router = APIRouter()


@router.put(
    "/workers/{worker_id}/booking-coverage",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def replace_booking_coverage(
    worker_id: uuid.UUID,
    payload: BookingCoverageWrite,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(UserRole.operations, UserRole.admin)),
):
    worker = await WorkforceRepository(session).get_worker(worker_id)
    if not worker:
        raise HTTPException(404, "Worker not found")

    existing_services = set(
        (
            await session.scalars(
                select(Service.id).where(
                    Service.id.in_(payload.service_ids),
                    Service.is_active.is_(True),
                )
            )
        ).all()
    )
    if existing_services != set(payload.service_ids):
        raise HTTPException(422, "Coverage contains an unavailable service")

    await session.execute(
        delete(ProviderServiceCoverage).where(
            ProviderServiceCoverage.worker_id == worker_id
        )
    )
    await session.execute(
        delete(ProviderWorkingHours).where(ProviderWorkingHours.worker_id == worker_id)
    )
    for service_id in payload.service_ids:
        for postal_code in sorted(set(payload.postal_codes)):
            session.add(
                ProviderServiceCoverage(
                    worker_id=worker_id,
                    service_id=service_id,
                    postal_code=postal_code,
                )
            )
    for weekday in sorted(set(payload.weekdays)):
        session.add(
            ProviderWorkingHours(
                worker_id=worker_id,
                weekday=weekday,
                start_time=payload.start_time,
                end_time=payload.end_time,
                capacity=payload.capacity,
            )
        )
    await session.commit()


@router.patch("/vendors/{vendor_id}/status", response_model=VendorRead)
async def set_vendor_status(
    vendor_id: uuid.UUID,
    payload: VendorStatusUpdate,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(UserRole.operations, UserRole.admin)),
):
    vendor = await WorkforceRepository(session).get_vendor(vendor_id, lock=True)
    if not vendor:
        raise HTTPException(404, "Vendor not found")
    vendor.status = payload.status
    await session.commit()
    await session.refresh(vendor)
    return vendor
