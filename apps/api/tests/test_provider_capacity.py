from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.core.errors import DomainError
from app.domains.booking.capacity import (
    CapacityLimit,
    CapacityUsage,
    capacity_consumption,
    ensure_capacity,
    hold_is_active,
    snapshot,
)
from app.domains.workforce.provider_schemas import AvailabilityExceptionPatch


def test_capacity_consumes_service_buffers_and_travel() -> None:
    assert capacity_consumption(90, 15, 0, 25) == 130


def test_minute_and_job_capacity_are_both_enforced() -> None:
    limit = CapacityLimit(max_jobs=4, max_minutes=600)
    partial = CapacityUsage(job_count=2, booking_minutes=210, buffer_minutes=45, travel_minutes=60)
    assert snapshot(limit, partial).remaining_minutes == 285
    with pytest.raises(DomainError) as minutes:
        ensure_capacity(limit, partial, 286)
    assert minutes.value.code == "NO_CAPACITY"
    with pytest.raises(DomainError) as jobs:
        ensure_capacity(limit, CapacityUsage(job_count=4, booking_minutes=100), 30)
    assert jobs.value.code == "NO_CAPACITY"


def test_holds_consume_capacity_until_expiry_only() -> None:
    now = datetime(2026, 8, 18, 12, tzinfo=UTC)
    assert hold_is_active("HELD", now + timedelta(minutes=30), now=now)
    assert not hold_is_active("HELD", now, now=now)
    assert not hold_is_active("RELEASED", now + timedelta(minutes=30), now=now)


def test_emergency_reserve_is_protected_from_regular_work() -> None:
    limit = CapacityLimit(
        max_jobs=6, max_minutes=600, emergency_reserved_jobs=1, emergency_reserved_minutes=120
    )
    regular = snapshot(limit, CapacityUsage(job_count=4, booking_minutes=470), emergency=False)
    assert (
        regular.max_job_count == 5
        and regular.total_minutes == 480
        and regular.remaining_minutes == 10
    )
    emergency = snapshot(limit, CapacityUsage(job_count=4, booking_minutes=470), emergency=True)
    assert emergency.max_job_count == 6 and emergency.remaining_minutes == 130


def test_concurrency_limit_rejects_overlapping_interval() -> None:
    with pytest.raises(DomainError) as conflict:
        ensure_capacity(CapacityLimit(6, 600), CapacityUsage(), 60, overlapping_jobs=1)
    assert conflict.value.code == "HOLD_CONFLICT"


def test_availability_exception_patch_requires_a_change_and_aware_timestamps() -> None:
    with pytest.raises(ValidationError):
        AvailabilityExceptionPatch()
    with pytest.raises(ValidationError):
        AvailabilityExceptionPatch(start_at=datetime(2026, 8, 18, 12))
    patch = AvailabilityExceptionPatch(reason="TRAINING")
    assert patch.reason == "TRAINING"
