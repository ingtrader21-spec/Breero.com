import pytest

from app.core.errors import DomainError
from app.domains.booking.lifecycle import ensure_transition
from app.domains.booking.models import BookingStatus


def test_happy_path_transitions_are_explicit() -> None:
    path = [
        BookingStatus.DRAFT, BookingStatus.REQUESTED, BookingStatus.ADDRESS_VALIDATED,
        BookingStatus.COVERAGE_CONFIRMED, BookingStatus.AVAILABILITY_FOUND,
        BookingStatus.CAPACITY_HELD, BookingStatus.AWAITING_ASSIGNMENT,
        BookingStatus.PROVIDER_ASSIGNED, BookingStatus.CONFIRMED,
        BookingStatus.EN_ROUTE, BookingStatus.IN_PROGRESS, BookingStatus.COMPLETED,
    ]
    for current, target in zip(path, path[1:]):
        ensure_transition(current, target)


def test_arbitrary_or_terminal_state_writes_are_rejected() -> None:
    with pytest.raises(DomainError) as skipped:
        ensure_transition(BookingStatus.REQUESTED, BookingStatus.CONFIRMED)
    assert skipped.value.code == "INVALID_STATE_TRANSITION"
    with pytest.raises(DomainError):
        ensure_transition(BookingStatus.COMPLETED, BookingStatus.IN_PROGRESS)
