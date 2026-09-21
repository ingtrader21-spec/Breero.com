from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.errors import DomainError


@dataclass(frozen=True)
class CapacityLimit:
    max_jobs: int
    max_minutes: int
    max_concurrent_jobs: int = 1
    emergency_reserved_jobs: int = 0
    emergency_reserved_minutes: int = 0


@dataclass(frozen=True)
class CapacityUsage:
    job_count: int = 0
    booking_minutes: int = 0
    hold_count: int = 0
    hold_minutes: int = 0
    buffer_minutes: int = 0
    travel_minutes: int = 0

    @property
    def reserved_minutes(self) -> int:
        return self.booking_minutes + self.hold_minutes + self.buffer_minutes + self.travel_minutes


@dataclass(frozen=True)
class CapacitySnapshot:
    total_minutes: int
    reserved_minutes: int
    booking_minutes: int
    hold_minutes: int
    buffer_minutes: int
    travel_minutes: int
    remaining_minutes: int
    job_count: int
    hold_count: int
    max_job_count: int


def capacity_consumption(
    service_minutes: int,
    before_buffer_minutes: int = 0,
    after_buffer_minutes: int = 0,
    estimated_travel_minutes: int = 0,
) -> int:
    values = (service_minutes, before_buffer_minutes, after_buffer_minutes, estimated_travel_minutes)
    if service_minutes <= 0 or any(value < 0 for value in values):
        raise DomainError("INVALID_CAPACITY", "Capacity durations must be positive", 422)
    return sum(values)


def snapshot(limit: CapacityLimit, usage: CapacityUsage, *, emergency: bool = False) -> CapacitySnapshot:
    if limit.max_jobs <= 0 or limit.max_minutes <= 0 or limit.max_concurrent_jobs <= 0:
        raise DomainError("INVALID_CAPACITY", "Provider capacity limits must be positive", 422)
    max_jobs = limit.max_jobs if emergency else max(limit.max_jobs - limit.emergency_reserved_jobs, 0)
    max_minutes = limit.max_minutes if emergency else max(limit.max_minutes - limit.emergency_reserved_minutes, 0)
    reserved = usage.reserved_minutes
    return CapacitySnapshot(
        total_minutes=max_minutes,
        reserved_minutes=reserved,
        booking_minutes=usage.booking_minutes,
        hold_minutes=usage.hold_minutes,
        buffer_minutes=usage.buffer_minutes,
        travel_minutes=usage.travel_minutes,
        remaining_minutes=max(max_minutes - reserved, 0),
        job_count=usage.job_count + usage.hold_count,
        hold_count=usage.hold_count,
        max_job_count=max_jobs,
    )


def ensure_capacity(
    limit: CapacityLimit,
    usage: CapacityUsage,
    requested_minutes: int,
    *,
    overlapping_jobs: int = 0,
    emergency: bool = False,
) -> CapacitySnapshot:
    current = snapshot(limit, usage, emergency=emergency)
    if requested_minutes <= 0:
        raise DomainError("INVALID_CAPACITY", "Requested capacity must be positive", 422)
    if current.job_count >= current.max_job_count or requested_minutes > current.remaining_minutes:
        raise DomainError("NO_CAPACITY", "No appointments are available for the selected time", 409)
    if overlapping_jobs >= limit.max_concurrent_jobs:
        raise DomainError("HOLD_CONFLICT", "The selected provider interval is no longer available", 409)
    return current


def hold_is_active(status: str, expires_at: datetime, *, now: datetime | None = None) -> bool:
    current = now or datetime.now(UTC)
    if expires_at.tzinfo is None:
        raise DomainError("INVALID_HOLD", "Hold expiry must be timezone-aware", 500)
    return status == "HELD" and expires_at > current
