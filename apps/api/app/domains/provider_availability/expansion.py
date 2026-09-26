"""Pure expansion of weekly local-time rules into concrete UTC intervals.

Rules are interpreted in their own IANA timezone per calendar day, so a 09:00-17:00
window is 09:00-17:00 local on both sides of a daylight-saving transition. Blackouts
without a worker apply to every rule; worker blackouts only to that worker's rules.
"""

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class RuleWindow:
    worker_id: uuid.UUID | None
    weekday: int
    start_time: time
    end_time: time
    timezone: str
    valid_from: date | None = None
    valid_until: date | None = None


@dataclass(frozen=True)
class Blackout:
    worker_id: uuid.UUID | None
    starts_at: datetime
    ends_at: datetime


@dataclass(frozen=True)
class Interval:
    worker_id: uuid.UUID | None
    starts_at: datetime
    ends_at: datetime
    timezone: str


def _local_dates(window_start: datetime, window_end: datetime, zone: ZoneInfo) -> Iterable[date]:
    first = window_start.astimezone(zone).date() - timedelta(days=1)
    last = window_end.astimezone(zone).date() + timedelta(days=1)
    current = first
    while current <= last:
        yield current
        current += timedelta(days=1)


def _subtract(
    start: datetime, end: datetime, blocks: Sequence[tuple[datetime, datetime]]
) -> list[tuple[datetime, datetime]]:
    pieces = [(start, end)]
    for block_start, block_end in blocks:
        next_pieces: list[tuple[datetime, datetime]] = []
        for piece_start, piece_end in pieces:
            if block_end <= piece_start or block_start >= piece_end:
                next_pieces.append((piece_start, piece_end))
                continue
            if block_start > piece_start:
                next_pieces.append((piece_start, block_start))
            if block_end < piece_end:
                next_pieces.append((block_end, piece_end))
        pieces = next_pieces
    return pieces


def expand(
    rules: Sequence[RuleWindow],
    blackouts: Sequence[Blackout],
    window_start: datetime,
    window_end: datetime,
) -> list[Interval]:
    if window_start.tzinfo is None or window_end.tzinfo is None:
        raise ValueError("preview window must be timezone-aware")
    window_start = window_start.astimezone(UTC)
    window_end = window_end.astimezone(UTC)
    if window_start >= window_end:
        return []

    intervals: list[Interval] = []
    for rule in rules:
        zone = ZoneInfo(rule.timezone)
        blocks = sorted(
            (item.starts_at.astimezone(UTC), item.ends_at.astimezone(UTC))
            for item in blackouts
            if item.worker_id is None or item.worker_id == rule.worker_id
        )
        for local_day in _local_dates(window_start, window_end, zone):
            if local_day.weekday() != rule.weekday:
                continue
            if rule.valid_from and local_day < rule.valid_from:
                continue
            if rule.valid_until and local_day > rule.valid_until:
                continue
            start = datetime.combine(local_day, rule.start_time, tzinfo=zone).astimezone(UTC)
            end = datetime.combine(local_day, rule.end_time, tzinfo=zone).astimezone(UTC)
            start, end = max(start, window_start), min(end, window_end)
            if start >= end:
                continue
            for piece_start, piece_end in _subtract(start, end, blocks):
                intervals.append(
                    Interval(
                        worker_id=rule.worker_id,
                        starts_at=piece_start,
                        ends_at=piece_end,
                        timezone=rule.timezone,
                    )
                )
    intervals.sort(key=lambda item: (item.starts_at, str(item.worker_id or "")))
    return intervals


def windows_overlap(first: RuleWindow, second: RuleWindow) -> bool:
    """True when two weekly windows for the same scope could be active at once."""

    if first.weekday != second.weekday:
        return False
    if first.start_time >= second.end_time or second.start_time >= first.end_time:
        return False
    first_from = first.valid_from or date.min
    first_until = first.valid_until or date.max
    second_from = second.valid_from or date.min
    second_until = second.valid_until or date.max
    return first_from <= second_until and second_from <= first_until
