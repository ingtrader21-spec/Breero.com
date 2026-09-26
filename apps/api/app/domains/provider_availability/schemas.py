import re
import uuid
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

IANA_ZONE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_+\-]*(/[A-Za-z0-9_+\-]+){1,2}$")
MAX_BLACKOUT_LENGTH = timedelta(days=366)
MAX_PREVIEW_LENGTH = timedelta(days=31)


def validate_timezone(value: str) -> str:
    name = value.strip()
    if name != "UTC" and not IANA_ZONE_RE.fullmatch(name):
        raise ValueError("timezone must be an IANA timezone identifier such as America/Chicago")
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("timezone is not a known IANA timezone") from exc
    return name


def validate_wall_time(value: time) -> time:
    if value.tzinfo is not None:
        raise ValueError("availability times are local wall-clock times without an offset")
    if value.second or value.microsecond:
        raise ValueError("availability times use minute precision")
    return value


def validate_rule_values(
    *,
    start_time: time,
    end_time: time,
    valid_from: date | None,
    valid_until: date | None,
) -> None:
    if start_time >= end_time:
        raise ValueError(
            "start_time must be before end_time; split overnight windows across two days"
        )
    if valid_from and valid_until and valid_from > valid_until:
        raise ValueError("valid_from must not be after valid_until")


def validate_blackout_values(starts_at: datetime, ends_at: datetime) -> None:
    if starts_at >= ends_at:
        raise ValueError("starts_at must be before ends_at")
    if ends_at - starts_at > MAX_BLACKOUT_LENGTH:
        raise ValueError("blackout periods may not exceed 366 days")


class AvailabilityRuleCreate(BaseModel):
    """Weekly window. ``weekday`` uses ISO order with Monday=0 through Sunday=6."""

    model_config = ConfigDict(extra="forbid")

    worker_id: uuid.UUID | None = None
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    timezone: str = Field(min_length=3, max_length=64)
    valid_from: date | None = None
    valid_until: date | None = None

    check_timezone = field_validator("timezone")(validate_timezone)
    check_times = field_validator("start_time", "end_time")(validate_wall_time)

    @model_validator(mode="after")
    def validate_window(self) -> "AvailabilityRuleCreate":
        validate_rule_values(
            start_time=self.start_time,
            end_time=self.end_time,
            valid_from=self.valid_from,
            valid_until=self.valid_until,
        )
        return self


class AvailabilityRuleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weekday: int | None = Field(default=None, ge=0, le=6)
    start_time: time | None = None
    end_time: time | None = None
    timezone: str | None = Field(default=None, min_length=3, max_length=64)
    valid_from: date | None = None
    valid_until: date | None = None

    @field_validator("timezone")
    @classmethod
    def check_timezone(cls, value: str | None) -> str | None:
        return None if value is None else validate_timezone(value)

    @field_validator("start_time", "end_time")
    @classmethod
    def check_times(cls, value: time | None) -> time | None:
        return None if value is None else validate_wall_time(value)

    @model_validator(mode="after")
    def validate_patch(self) -> "AvailabilityRuleUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one availability field is required")
        for required in ("weekday", "start_time", "end_time", "timezone"):
            if required in self.model_fields_set and getattr(self, required) is None:
                raise ValueError(f"{required} cannot be cleared")
        return self


class AvailabilityRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vendor_id: uuid.UUID
    worker_id: uuid.UUID | None
    weekday: int
    start_time: time
    end_time: time
    timezone: str
    valid_from: date | None
    valid_until: date | None
    version: int
    created_at: datetime
    updated_at: datetime


class BlackoutPeriodCreate(BaseModel):
    """Absolute interval. Offsets are required; values are stored in UTC."""

    model_config = ConfigDict(extra="forbid")

    worker_id: uuid.UUID | None = None
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    timezone: str = Field(min_length=3, max_length=64)
    reason: str | None = Field(default=None, max_length=500)

    check_timezone = field_validator("timezone")(validate_timezone)

    @model_validator(mode="after")
    def validate_period(self) -> "BlackoutPeriodCreate":
        self.starts_at = self.starts_at.astimezone(UTC)
        self.ends_at = self.ends_at.astimezone(UTC)
        validate_blackout_values(self.starts_at, self.ends_at)
        if self.reason is not None:
            self.reason = self.reason.strip() or None
        return self


class BlackoutPeriodUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    timezone: str | None = Field(default=None, min_length=3, max_length=64)
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("timezone")
    @classmethod
    def check_timezone(cls, value: str | None) -> str | None:
        return None if value is None else validate_timezone(value)

    @model_validator(mode="after")
    def validate_patch(self) -> "BlackoutPeriodUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one blackout field is required")
        for required in ("starts_at", "ends_at", "timezone"):
            if required in self.model_fields_set and getattr(self, required) is None:
                raise ValueError(f"{required} cannot be cleared")
        if self.starts_at is not None:
            self.starts_at = self.starts_at.astimezone(UTC)
        if self.ends_at is not None:
            self.ends_at = self.ends_at.astimezone(UTC)
        if self.reason is not None:
            self.reason = self.reason.strip() or None
        return self


class BlackoutPeriodRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vendor_id: uuid.UUID
    worker_id: uuid.UUID | None
    starts_at: datetime
    ends_at: datetime
    timezone: str
    reason: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class ProviderAvailabilityRead(BaseModel):
    rules: list[AvailabilityRuleRead]
    blackouts: list[BlackoutPeriodRead]
    consumed_by_scheduling: bool = Field(
        default=False,
        description=(
            "Provider-declared availability is not yet an input to booking, dispatch, "
            "or automatic assignment."
        ),
    )


class AvailabilityInterval(BaseModel):
    worker_id: uuid.UUID | None
    starts_at: datetime
    ends_at: datetime
    timezone: str


class AvailabilityPreviewRead(BaseModel):
    window_start: datetime
    window_end: datetime
    intervals: list[AvailabilityInterval]
