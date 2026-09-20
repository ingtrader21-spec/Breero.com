import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProviderServiceWrite(BaseModel):
    service_id: uuid.UUID


class ProviderServicePatch(BaseModel):
    requested_active: bool


class ProviderServiceRead(ProviderServiceWrite):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    active: bool
    approval_status: str


class ProviderServiceAreaWrite(BaseModel):
    area_type: str = Field(pattern="^(ZIP|ZIP_GROUP|CITY|COUNTY|RADIUS|SERVICE_ZONE)$")
    professional_id: uuid.UUID | None = None
    service_zone_id: uuid.UUID | None = None
    postal_code: str | None = Field(default=None, pattern=r"^\d{5}$")
    city: str | None = Field(default=None, min_length=2, max_length=120)
    county: str | None = Field(default=None, min_length=2, max_length=120)
    state: str | None = Field(default=None, min_length=2, max_length=3)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    radius_meters: int | None = Field(default=None, gt=0, le=500_000)

    @model_validator(mode="after")
    def required_dimension(self) -> "ProviderServiceAreaWrite":
        required = {
            "ZIP": self.postal_code,
            "ZIP_GROUP": self.postal_code,
            "CITY": self.city and self.state,
            "COUNTY": self.county and self.state,
            "SERVICE_ZONE": self.service_zone_id,
            "RADIUS": self.radius_meters and self.latitude is not None and self.longitude is not None,
        }
        if not required[self.area_type]:
            raise ValueError(f"{self.area_type} service area is missing its required dimension")
        return self


class ProviderServiceAreaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    area_type: str
    professional_id: uuid.UUID | None
    service_zone_id: uuid.UUID | None
    postal_code: str | None
    city: str | None
    county: str | None
    state: str | None
    radius_meters: int | None
    active: bool
    approval_status: str


class AvailabilityRuleWrite(BaseModel):
    professional_id: uuid.UUID
    day_of_week: int = Field(ge=0, le=6)
    start_local_time: time
    end_local_time: time
    available: bool = True
    emergency_only: bool = False
    timezone_id: str = Field(min_length=3, max_length=64)

    @model_validator(mode="after")
    def within_breero_hours(self) -> "AvailabilityRuleWrite":
        if self.start_local_time < time(7) or self.end_local_time > time(19):
            raise ValueError("Provider availability must remain within 07:00-19:00")
        if self.end_local_time <= self.start_local_time:
            raise ValueError("Availability end must follow start")
        if self.day_of_week == 6 and not self.emergency_only:
            raise ValueError("Sunday availability must be emergency-only")
        return self


class AvailabilityRuleRead(AvailabilityRuleWrite):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    professional_id: uuid.UUID = Field(validation_alias="provider_professional_id")
    id: uuid.UUID


class AvailabilityExceptionWrite(BaseModel):
    professional_id: uuid.UUID
    start_at: datetime
    end_at: datetime
    timezone_id: str = Field(min_length=3, max_length=64)
    reason: str = Field(pattern="^(VACATION|SICK|PERSONAL|TRAINING|VEHICLE|HOLIDAY|MANUAL_BLOCK|OTHER)$")

    @model_validator(mode="after")
    def valid_interval(self) -> "AvailabilityExceptionWrite":
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None or self.end_at <= self.start_at:
            raise ValueError("A timezone-aware increasing exception interval is required")
        return self


class AvailabilityExceptionPatch(BaseModel):
    start_at: datetime | None = None
    end_at: datetime | None = None
    timezone_id: str | None = Field(default=None, min_length=3, max_length=64)
    reason: str | None = Field(
        default=None,
        pattern="^(VACATION|SICK|PERSONAL|TRAINING|VEHICLE|HOLIDAY|MANUAL_BLOCK|OTHER)$",
    )

    @model_validator(mode="after")
    def valid_interval(self) -> "AvailabilityExceptionPatch":
        for value in (self.start_at, self.end_at):
            if value is not None and value.tzinfo is None:
                raise ValueError("Availability exception timestamps must be timezone-aware")
        if self.start_at is not None and self.end_at is not None and self.end_at <= self.start_at:
            raise ValueError("A timezone-aware increasing exception interval is required")
        if not self.model_fields_set:
            raise ValueError("At least one availability exception field is required")
        return self


class AvailabilityExceptionRead(AvailabilityExceptionWrite):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    status: str


class CapacityRuleWrite(BaseModel):
    professional_id: uuid.UUID | None = None
    max_jobs_daily: int = Field(ge=1, le=30)
    max_minutes_daily: int = Field(ge=30, le=720)
    max_concurrent_jobs: int = Field(default=1, ge=1, le=5)
    emergency_reserved_jobs: int = Field(default=0, ge=0, le=10)
    emergency_reserved_minutes: int = Field(default=0, ge=0, le=720)
    effective_from: date
    effective_until: date | None = None

    @model_validator(mode="after")
    def valid_limits(self) -> "CapacityRuleWrite":
        if self.emergency_reserved_jobs >= self.max_jobs_daily:
            raise ValueError("Emergency job reserve must be below daily jobs")
        if self.emergency_reserved_minutes >= self.max_minutes_daily:
            raise ValueError("Emergency minute reserve must be below daily minutes")
        if self.effective_until and self.effective_until < self.effective_from:
            raise ValueError("Capacity effective range is invalid")
        return self


class CapacityRuleRead(CapacityRuleWrite):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    provider_id: uuid.UUID


class CapacityDay(BaseModel):
    date: date
    total_minutes: int
    reserved_minutes: int
    booking_minutes: int
    buffer_minutes: int
    remaining_minutes: int
    job_count: int
    max_job_count: int
