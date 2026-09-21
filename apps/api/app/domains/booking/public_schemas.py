import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field


class PublicAddressInput(BaseModel):
    line1: str = Field(min_length=3, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=2, max_length=120)
    state: str = Field(min_length=2, max_length=3)
    postal_code: str = Field(pattern=r"^\d{5}(?:-\d{4})?$")

    def single_line(self) -> str:
        return ", ".join(
            value
            for value in (self.line1, self.line2, self.city, self.state, self.postal_code, "US")
            if value
        )


class PublicAvailabilityRequest(BaseModel):
    service_id: str = Field(min_length=1, max_length=100)
    address: PublicAddressInput
    requested_date: date
    emergency: bool = False


class PublicSlot(BaseModel):
    start_local: str
    end_local: str


class PublicAvailabilityResponse(BaseModel):
    timezone: str
    date: date
    address_id: uuid.UUID
    slots: list[PublicSlot]
    reason: str | None = None


class CapacityHoldCreate(BaseModel):
    service_id: uuid.UUID
    address_id: uuid.UUID
    start_local: datetime
    timezone: str = Field(min_length=3, max_length=64)
    emergency: bool = False


class CapacityHoldRead(BaseModel):
    hold_id: uuid.UUID
    status: str
    expires_at: datetime
    expires_in_seconds: int
    timezone: str
    start_local: datetime
    end_local: datetime


class BookingCustomerInput(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: str = Field(min_length=5, max_length=40)


class BookingRequestCreate(BaseModel):
    hold_id: uuid.UUID
    booking_session: str = Field(min_length=16, max_length=512)
    customer: BookingCustomerInput
    notes: str | None = Field(default=None, max_length=4000)


class BookingRequestRead(BaseModel):
    public_reference: str
    status: str
    timezone: str
    start_at_utc: datetime
    end_at_utc: datetime
    account_created: bool
    access_token: str | None = None
    refresh_token: str | None = None
    password_set_required: bool = False
