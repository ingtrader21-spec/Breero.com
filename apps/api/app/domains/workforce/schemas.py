import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from .models import (
    ProviderApplicationStatus,
    ProviderCredentialType,
    VendorStatus,
    WorkerStatus,
)


class VendorCreate(BaseModel):
    legal_name: str = Field(min_length=1, max_length=180)
    display_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=5, max_length=32)
    owner_user_id: uuid.UUID | None = None
    capabilities: list[str] = Field(default_factory=list)
    service_radius_meters: int = Field(default=40000, ge=1000, le=500000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def coordinates_are_a_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be supplied together")
        return self


class VendorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    legal_name: str
    display_name: str
    email: str
    phone: str
    owner_user_id: uuid.UUID | None
    status: VendorStatus
    capabilities: list
    service_radius_meters: int


class VendorStatusUpdate(BaseModel):
    status: VendorStatus


class WorkerCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    phone: str = Field(min_length=5, max_length=32)
    skills: list[str] = Field(default_factory=list)
    user_id: uuid.UUID | None = None


class WorkerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    vendor_id: uuid.UUID
    user_id: uuid.UUID | None
    first_name: str
    last_name: str
    email: str
    phone: str
    status: WorkerStatus
    skills: list
    available: bool


class ProviderWorkerCreate(BaseModel):
    """Provider self-service team member; account linking and activation stay with BREERO."""

    model_config = ConfigDict(extra="forbid")
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    phone: str = Field(min_length=5, max_length=32)

    @model_validator(mode="after")
    def normalize(self):
        self.first_name = self.first_name.strip()
        self.last_name = self.last_name.strip()
        self.phone = self.phone.strip()
        if not self.first_name or not self.last_name:
            raise ValueError("first_name and last_name are required")
        return self


class ProviderWorkerRead(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    phone: str
    status: WorkerStatus
    available: bool
    skills: list
    has_account: bool
    is_account_owner: bool


class ProviderWorkerList(BaseModel):
    items: list[ProviderWorkerRead]
    total: int


class LocationUpdate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_meters: int | None = Field(default=None, ge=0, le=10000)


class BookingCoverageWrite(BaseModel):
    service_ids: list[uuid.UUID] = Field(min_length=1, max_length=12)
    postal_codes: list[str] = Field(min_length=1, max_length=500)
    weekdays: list[int] = Field(
        default_factory=lambda: list(range(7)), min_length=1, max_length=7
    )
    start_time: time = time(7)
    end_time: time = time(19)
    capacity: int = 1

    @model_validator(mode="after")
    def enforce_booking_policy(self):
        if self.start_time != time(7) or self.end_time != time(19) or self.capacity != 1:
            raise ValueError("Provider hours must be 07:00-19:00 with capacity one")
        if any(day < 0 or day > 6 for day in self.weekdays):
            raise ValueError("Weekdays must be between 0 and 6")
        if any(not code.isdigit() or len(code) != 5 for code in self.postal_codes):
            raise ValueError("Coverage requires five-digit ZIP codes")
        return self


class ProviderCredentialWrite(BaseModel):
    credential_type: ProviderCredentialType
    jurisdiction: str = Field(min_length=2, max_length=3)
    reference_last4: str | None = Field(default=None, min_length=4, max_length=4)
    expires_on: date
    verified: bool = False


class ProviderCredentialRead(ProviderCredentialWrite):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    vendor_id: uuid.UUID


class ProviderProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    legal_name: str | None = Field(default=None, min_length=1, max_length=180)
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    phone: str | None = Field(default=None, min_length=5, max_length=32)
    service_radius_meters: int | None = Field(default=None, ge=1000, le=500000)


class ProviderRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=1, max_length=160)
    legal_name: str = Field(min_length=1, max_length=180)
    display_name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=5, max_length=32)


class ProviderOnboardingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    identity: dict | None = None
    business: dict | None = None
    contact_details: dict | None = None
    services: list[uuid.UUID] | None = Field(default=None, max_length=100)
    skills: list[str] | None = Field(default=None, max_length=100)
    service_areas: list[dict] | None = Field(default=None, max_length=500)
    postal_codes: list[str] | None = Field(default=None, max_length=500)
    availability: dict | None = None
    capacity: dict | None = None
    licenses: list[dict] | None = Field(default=None, max_length=100)
    insurance: list[dict] | None = Field(default=None, max_length=100)
    compliance_documents: list[uuid.UUID] | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def normalize_postal_codes(self):
        if self.postal_codes is None:
            return self
        normalized: list[str] = []
        for raw in self.postal_codes:
            code = raw.strip()
            if len(code) not in {5, 10} or not code[:5].isdigit():
                raise ValueError("postal_codes require ZIP or ZIP+4 values")
            if len(code) == 10 and (code[5] != "-" or not code[6:].isdigit()):
                raise ValueError("postal_codes require ZIP or ZIP+4 values")
            if code not in normalized:
                normalized.append(code)
        self.postal_codes = normalized
        return self


class ProviderApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    vendor_id: uuid.UUID
    status: ProviderApplicationStatus
    identity: dict
    business: dict
    contact_details: dict
    services: list
    skills: list
    service_areas: list
    postal_codes: list
    availability: dict
    capacity: dict
    licenses: list
    insurance: list
    compliance_documents: list
    version: int
    submitted_at: object | None
    decided_at: object | None
    reviewed_by: uuid.UUID | None
    decision_reason: str | None
    requested_information: str | None


class ProviderOnboardingChecklist(BaseModel):
    application_id: uuid.UUID
    status: ProviderApplicationStatus
    version: int
    editable: bool
    submittable: bool
    missing: list[str]
    requested_information: str | None
    decision_reason: str | None
    submitted_at: datetime | None
    decided_at: datetime | None


class ProviderRegistrationResponse(BaseModel):
    user_id: uuid.UUID
    vendor: VendorRead
    application: ProviderApplicationRead
    access_token: str
    refresh_token: str
    expires_in: int
    refresh_expires_in: int


class ProviderApplicationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=3, max_length=1000)


class ProviderApplicationList(BaseModel):
    items: list[ProviderApplicationRead]
    total: int
