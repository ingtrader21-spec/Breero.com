import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.domains.auth.dependencies import require_roles
from app.domains.auth.models import User, UserRole
from app.domains.jobs.schemas import JobRead
from app.domains.workforce.provider_schemas import (
    AvailabilityExceptionPatch,
    AvailabilityExceptionRead,
    AvailabilityExceptionWrite,
    AvailabilityRuleRead,
    AvailabilityRuleWrite,
    CapacityDay,
    CapacityRuleRead,
    CapacityRuleWrite,
    ProviderServiceAreaRead,
    ProviderServiceAreaWrite,
    ProviderServicePatch,
    ProviderServiceRead,
    ProviderServiceWrite,
)
from app.domains.workforce.provider_service import ProviderPortalService
from app.domains.workforce.schemas import VendorRead

router = APIRouter()
provider_user = require_roles(UserRole.vendor_admin, UserRole.technician)


@router.get("/profile", response_model=VendorRead)
async def profile(
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(provider_user)],
):
    vendor, _ = await ProviderPortalService(session, user).context()
    return vendor


@router.get("/jobs", response_model=list[JobRead])
async def jobs(
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(provider_user)],
):
    return await ProviderPortalService(session, user).jobs()


@router.get("/jobs/{job_id}", response_model=JobRead)
async def job(
    job_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(provider_user)],
):
    return await ProviderPortalService(session, user).job(job_id)


@router.get("/services", response_model=list[ProviderServiceRead])
async def services(
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(provider_user)],
):
    return await ProviderPortalService(session, user).services()


@router.post("/services", response_model=ProviderServiceRead, status_code=201)
async def add_service(
    data: ProviderServiceWrite,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.vendor_admin))],
):
    return await ProviderPortalService(session, user).add_service(data.service_id)


@router.delete("/services/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_service(
    item_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.vendor_admin))],
) -> None:
    await ProviderPortalService(session, user).remove_service(item_id)


@router.patch("/services/{item_id}", response_model=ProviderServiceRead)
async def change_service(
    item_id: uuid.UUID,
    data: ProviderServicePatch,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.vendor_admin))],
):
    return await ProviderPortalService(session, user).change_service(
        item_id, data.requested_active
    )


@router.get("/service-areas", response_model=list[ProviderServiceAreaRead])
async def service_areas(
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(provider_user)],
):
    return await ProviderPortalService(session, user).areas()


@router.post("/service-areas", response_model=ProviderServiceAreaRead, status_code=201)
async def add_service_area(
    data: ProviderServiceAreaWrite,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.vendor_admin))],
):
    return await ProviderPortalService(session, user).add_area(data)


@router.patch("/service-areas/{item_id}", response_model=ProviderServiceAreaRead)
async def update_service_area(
    item_id: uuid.UUID,
    data: ProviderServiceAreaWrite,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.vendor_admin))],
):
    return await ProviderPortalService(session, user).update_area(item_id, data)


@router.delete("/service-areas/{item_id}", status_code=204)
async def remove_service_area(
    item_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.vendor_admin))],
) -> None:
    await ProviderPortalService(session, user).remove_area(item_id)


@router.get("/availability", response_model=list[AvailabilityRuleRead])
async def availability(
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(provider_user)],
):
    return await ProviderPortalService(session, user).availability()


@router.put("/availability", response_model=list[AvailabilityRuleRead])
async def replace_availability(
    data: list[AvailabilityRuleWrite],
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.vendor_admin))],
):
    return await ProviderPortalService(session, user).replace_availability(data)


@router.get("/availability/exceptions", response_model=list[AvailabilityExceptionRead])
async def exceptions(
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(provider_user)],
):
    return await ProviderPortalService(session, user).exceptions()


@router.post(
    "/availability/exceptions", response_model=AvailabilityExceptionRead, status_code=201
)
async def add_exception(
    data: AvailabilityExceptionWrite,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.vendor_admin))],
):
    return await ProviderPortalService(session, user).add_exception(data)


@router.patch("/availability/exceptions/{item_id}", response_model=AvailabilityExceptionRead)
async def update_exception(
    item_id: uuid.UUID,
    data: AvailabilityExceptionPatch,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.vendor_admin))],
):
    return await ProviderPortalService(session, user).update_exception(item_id, data)


@router.delete("/availability/exceptions/{item_id}", status_code=204)
async def remove_exception(
    item_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.vendor_admin))],
) -> None:
    await ProviderPortalService(session, user).remove_exception(item_id)


@router.get("/capacity", response_model=list[CapacityRuleRead])
async def capacity(
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(provider_user)],
):
    return await ProviderPortalService(session, user).capacity()


@router.patch("/capacity", response_model=CapacityRuleRead)
async def set_capacity(
    data: CapacityRuleWrite,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.vendor_admin))],
    _: Annotated[None, Depends(rate_limit("provider-capacity", 30, 60))],
):
    return await ProviderPortalService(session, user).set_capacity(data)


@router.get("/capacity/calendar", response_model=list[CapacityDay])
async def capacity_calendar(
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(provider_user)],
    start: date | None = None,
    days: int = 7,
):
    if days < 1 or days > 31:
        raise DomainError("INVALID_DATE_RANGE", "Capacity calendar supports 1 to 31 days", 422)
    return await ProviderPortalService(session, user).capacity_calendar(start or date.today(), days)
