import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.customer.dependencies import customer_for, owned_address
from app.api.v1.customer.schemas import (
    AddressInput,
    AddressRead,
)
from app.db.session import get_db
from app.domains.auth.dependencies import current_user
from app.domains.auth.models import User
from app.domains.booking.models import Address, Booking

router = APIRouter()

@router.get("/addresses", response_model=list[AddressRead])
async def addresses(
    user: Annotated[User, Depends(current_user)], session: Annotated[AsyncSession, Depends(get_db)]
) -> list[Address]:
    customer = await customer_for(session, user)
    return list(
        (
            await session.scalars(
                select(Address)
                .where(Address.customer_id == customer.id)
                .order_by(Address.created_at.desc())
            )
        ).all()
    )

@router.post("/addresses", response_model=AddressRead, status_code=201)
async def add_address(
    data: AddressInput,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Address:
    from app.domains.booking.schemas import AddressValidateRequest
    from app.domains.booking.service import AddressService

    customer = await customer_for(session, user)
    validated = await AddressService(session).validate(
        AddressValidateRequest(
            address=", ".join(
                value for value in (data.line1, data.line2, data.city, data.state, data.postal_code, "US") if value
            )
        )
    )
    if not validated.serviceable or not validated.address_id:
        raise HTTPException(422, "Address is outside an active service area")
    address = await session.get(Address, validated.address_id)
    if not address:
        raise HTTPException(500, "Validated address was not persisted")
    if data.is_default:
        await session.execute(
            update(Address)
            .where(Address.customer_id == customer.id)
            .values(is_default=False)
        )
    address.customer_id = customer.id
    address.label = data.label
    address.line2 = data.line2
    address.is_default = data.is_default
    await session.commit()
    await session.refresh(address)
    return address

@router.get("/addresses/{address_id}", response_model=AddressRead)
async def get_address(
    address_id: uuid.UUID,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Address:
    return await owned_address(session, await customer_for(session, user), address_id)

@router.patch("/addresses/{address_id}", response_model=AddressRead)
async def update_address(
    address_id: uuid.UUID,
    data: AddressInput,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Address:
    from app.domains.booking.schemas import AddressValidateRequest
    from app.domains.booking.service import AddressService

    address = await owned_address(session, await customer_for(session, user), address_id)
    if await session.scalar(select(Booking.id).where(Booking.address_id == address.id).limit(1)):
        raise HTTPException(409, "Booked addresses are immutable; add a new address instead")
    validated = await AddressService(session).validate(
        AddressValidateRequest(
            address=", ".join(
                value
                for value in (
                    data.line1,
                    data.line2,
                    data.city,
                    data.state,
                    data.postal_code,
                    "US",
                )
                if value
            )
        )
    )
    if not validated.serviceable or not validated.address_id:
        raise HTTPException(422, "Address is outside an active service area")
    replacement = await session.get(Address, validated.address_id)
    if not replacement:
        raise HTTPException(500, "Validated address was not persisted")
    if data.is_default:
        customer = await customer_for(session, user)
        await session.execute(
            update(Address)
            .where(Address.customer_id == customer.id, Address.id != address.id)
            .values(is_default=False)
        )
    for field in (
        "formatted_address",
        "line1",
        "city",
        "state_code",
        "postal_code",
        "postal_code_plus4",
        "country_code",
        "location",
        "service_area_id",
        "service_zone_id",
        "geocoding_provider",
        "timezone_name",
        "timezone_source",
        "address_validation_status",
    ):
        setattr(address, field, getattr(replacement, field))
    address.line2 = data.line2
    address.label = data.label
    address.is_default = data.is_default
    await session.delete(replacement)
    await session.commit()
    return address

@router.delete("/addresses/{address_id}", status_code=204)
async def delete_address(
    address_id: uuid.UUID,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    address = await owned_address(session, await customer_for(session, user), address_id)
    in_use = await session.scalar(
        select(Booking.id).where(Booking.address_id == address.id).limit(1)
    )
    if in_use:
        raise HTTPException(409, "Address is referenced by a booking")
    await session.delete(address)
    await session.commit()
