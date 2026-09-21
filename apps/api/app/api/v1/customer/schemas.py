import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.domains.payments.models import PaymentPurpose, PaymentStatus


class ProfilePatch(BaseModel):
    full_name: str | None = Field(None, min_length=1, max_length=160)
    phone: str | None = Field(None, min_length=3, max_length=40)

class ProfileRead(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    phone: str
    email_verified: bool

class AddressInput(BaseModel):
    label: str = Field(default="Home", pattern="^(Home|Rental property|Office|Other)$")
    line1: str = Field(min_length=1, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=1, max_length=120)
    state: str = Field(min_length=2, max_length=3)
    postal_code: str = Field(pattern=r"^\d{5}(?:-\d{4})?$")
    country_code: str = Field(default="US", pattern="^US$")
    is_default: bool = False

class AddressRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    label: str
    line1: str
    line2: str | None
    city: str
    state_code: str | None
    postal_code: str
    postal_code_plus4: str | None
    country_code: str
    timezone_name: str
    address_validation_status: str
    is_default: bool

class Page(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int

class BookingRescheduleRequest(BaseModel):
    hold_id: uuid.UUID
    booking_session: str = Field(min_length=16, max_length=512)

class CustomerPaymentRead(BaseModel):
    id: uuid.UUID
    booking_id: uuid.UUID | None
    quote_id: uuid.UUID | None
    payment_purpose: PaymentPurpose
    provider: str
    status: PaymentStatus
    amount_minor: int
    currency: str
    captured_amount_minor: int
    refunded_amount_minor: int
    failure_code: str | None
    created_at: datetime
    updated_at: datetime
