from dataclasses import dataclass
from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.errors import DomainError

OPEN_LOCAL = time(7, 0)
CLOSE_LOCAL = time(19, 0)


@dataclass(frozen=True)
class LocalizedInterval:
    start_utc: datetime
    end_utc: datetime
    timezone_id: str


def timezone(timezone_id: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_id)
    except ZoneInfoNotFoundError as exc:
        raise DomainError("TIMEZONE_UNRESOLVED", "Service address timezone is invalid", 422) from exc


def local_to_utc(local_value: datetime, timezone_id: str, *, fold: int | None = None) -> datetime:
    """Resolve a naive wall-clock value without guessing across a DST fold or gap."""
    if local_value.tzinfo is not None:
        raise DomainError("INVALID_LOCAL_TIME", "Local appointment time must not include an offset", 422)
    zone = timezone(timezone_id)
    candidates: list[datetime] = []
    for candidate_fold in (0, 1):
        aware = local_value.replace(tzinfo=zone, fold=candidate_fold)
        round_trip = aware.astimezone(UTC).astimezone(zone)
        if round_trip.replace(tzinfo=None) == local_value and round_trip.fold == candidate_fold:
            candidates.append(aware)
    unique = {candidate.utcoffset() for candidate in candidates}
    if not candidates:
        raise DomainError("NONEXISTENT_LOCAL_TIME", "Selected local time does not exist", 422)
    if len(unique) > 1 and fold is None:
        raise DomainError("AMBIGUOUS_LOCAL_TIME", "Selected local time occurs twice; choose an offset", 422)
    selected_fold = fold if fold is not None else candidates[0].fold
    selected = next((candidate for candidate in candidates if candidate.fold == selected_fold), None)
    if selected is None:
        raise DomainError("INVALID_LOCAL_TIME", "Selected local-time fold is invalid", 422)
    return selected.astimezone(UTC)


def local_interval(
    start_local: datetime,
    end_local: datetime,
    timezone_id: str,
    *,
    start_fold: int | None = None,
    end_fold: int | None = None,
) -> LocalizedInterval:
    start_utc = local_to_utc(start_local, timezone_id, fold=start_fold)
    end_utc = local_to_utc(end_local, timezone_id, fold=end_fold)
    if end_utc <= start_utc:
        raise DomainError("INVALID_TIME_RANGE", "Appointment end must follow its start", 422)
    return LocalizedInterval(start_utc=start_utc, end_utc=end_utc, timezone_id=timezone_id)


def enforce_breero_hours(
    start_local: datetime,
    end_local: datetime,
    *,
    service_emergency_eligible: bool,
    provider_sunday_emergency_enabled: bool,
    open_local: time = OPEN_LOCAL,
    close_local: time = CLOSE_LOCAL,
    emergency_only: bool | None = None,
) -> None:
    if start_local.date() != end_local.date() or start_local.time() < open_local or end_local.time() > close_local:
        raise DomainError("OUTSIDE_OPERATING_HOURS", "The requested time is outside BREERO operating hours", 422)
    restricted = start_local.weekday() == 6 if emergency_only is None else emergency_only
    if restricted and not (
        service_emergency_eligible and provider_sunday_emergency_enabled
    ):
        raise DomainError("SUNDAY_EMERGENCY_ONLY", "Sunday scheduling is limited to eligible emergency service", 422)
