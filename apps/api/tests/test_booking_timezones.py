from datetime import UTC, datetime, timedelta

import pytest

from app.core.errors import DomainError
from app.domains.booking.timezones import enforce_breero_hours, local_interval, local_to_utc


@pytest.mark.parametrize(
    ("timezone_id", "expected_hour"),
    [
        ("America/New_York", 14),
        ("America/Chicago", 15),
        ("America/Denver", 16),
        ("America/Phoenix", 17),
        ("America/Los_Angeles", 17),
        ("America/Anchorage", 18),
        ("Pacific/Honolulu", 20),
    ],
)
def test_us_service_timezone_controls_utc_conversion(timezone_id: str, expected_hour: int) -> None:
    resolved = local_to_utc(datetime(2026, 8, 18, 10), timezone_id)
    assert resolved == datetime(2026, 8, 18, expected_hour, tzinfo=UTC)


def test_spring_forward_nonexistent_time_is_rejected() -> None:
    with pytest.raises(DomainError, match="does not exist") as exc_info:
        local_to_utc(datetime(2026, 3, 8, 2, 30), "America/New_York")
    assert exc_info.value.code == "NONEXISTENT_LOCAL_TIME"


def test_fall_back_requires_explicit_fold_and_produces_distinct_instants() -> None:
    local = datetime(2026, 11, 1, 1, 30)
    with pytest.raises(DomainError) as exc_info:
        local_to_utc(local, "America/New_York")
    assert exc_info.value.code == "AMBIGUOUS_LOCAL_TIME"
    first = local_to_utc(local, "America/New_York", fold=0)
    second = local_to_utc(local, "America/New_York", fold=1)
    assert second - first == timedelta(hours=1)


@pytest.mark.parametrize("timezone_id", ["America/Phoenix", "Pacific/Honolulu"])
def test_non_dst_zones_have_no_spring_gap(timezone_id: str) -> None:
    assert local_to_utc(datetime(2026, 3, 8, 2, 30), timezone_id).tzinfo is UTC


def test_operating_hour_boundaries_and_sunday_policy() -> None:
    with pytest.raises(DomainError) as before_open:
        enforce_breero_hours(
            datetime(2026, 8, 17, 6, 59),
            datetime(2026, 8, 17, 8),
            service_emergency_eligible=False,
            provider_sunday_emergency_enabled=False,
        )
    assert before_open.value.code == "OUTSIDE_OPERATING_HOURS"
    enforce_breero_hours(
        datetime(2026, 8, 17, 7),
        datetime(2026, 8, 17, 9),
        service_emergency_eligible=False,
        provider_sunday_emergency_enabled=False,
    )
    enforce_breero_hours(
        datetime(2026, 8, 22, 17),
        datetime(2026, 8, 22, 19),
        service_emergency_eligible=False,
        provider_sunday_emergency_enabled=False,
    )
    with pytest.raises(DomainError) as sunday:
        enforce_breero_hours(
            datetime(2026, 8, 23, 7),
            datetime(2026, 8, 23, 9),
            service_emergency_eligible=False,
            provider_sunday_emergency_enabled=True,
        )
    assert sunday.value.code == "SUNDAY_EMERGENCY_ONLY"
    enforce_breero_hours(
        datetime(2026, 8, 23, 7),
        datetime(2026, 8, 23, 9),
        service_emergency_eligible=True,
        provider_sunday_emergency_enabled=True,
    )


def test_interval_uses_service_timezone_and_utc_storage() -> None:
    interval = local_interval(
        datetime(2026, 8, 18, 10), datetime(2026, 8, 18, 12), "America/Chicago"
    )
    assert interval.start_utc == datetime(2026, 8, 18, 15, tzinfo=UTC)
    assert interval.end_utc == datetime(2026, 8, 18, 17, tzinfo=UTC)
