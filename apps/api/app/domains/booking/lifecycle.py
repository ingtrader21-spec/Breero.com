from app.core.errors import DomainError
from app.domains.booking.models import BookingStatus

ALLOWED_TRANSITIONS: dict[BookingStatus, frozenset[BookingStatus]] = {
    BookingStatus.DRAFT: frozenset({BookingStatus.REQUESTED, BookingStatus.EXPIRED}),
    BookingStatus.REQUESTED: frozenset(
        {BookingStatus.PENDING_REVIEW, BookingStatus.ADDRESS_VALIDATED, BookingStatus.CANCELLED}
    ),
    BookingStatus.PENDING_REVIEW: frozenset(
        {BookingStatus.ADDRESS_VALIDATED, BookingStatus.NO_COVERAGE, BookingStatus.CANCELLED}
    ),
    BookingStatus.ADDRESS_VALIDATED: frozenset(
        {BookingStatus.COVERAGE_CONFIRMED, BookingStatus.NO_COVERAGE, BookingStatus.CANCELLED}
    ),
    BookingStatus.COVERAGE_CONFIRMED: frozenset(
        {BookingStatus.AVAILABILITY_FOUND, BookingStatus.NO_CAPACITY, BookingStatus.QUOTE_REQUIRED, BookingStatus.CANCELLED}
    ),
    BookingStatus.AVAILABILITY_FOUND: frozenset(
        {BookingStatus.CAPACITY_HELD, BookingStatus.NO_CAPACITY, BookingStatus.CANCELLED}
    ),
    BookingStatus.CAPACITY_HELD: frozenset(
        {BookingStatus.AWAITING_ASSIGNMENT, BookingStatus.PENDING_MANUAL_DISPATCH, BookingStatus.EXPIRED, BookingStatus.CANCELLED}
    ),
    BookingStatus.AWAITING_ASSIGNMENT: frozenset(
        {BookingStatus.PROVIDER_ASSIGNED, BookingStatus.NO_CAPACITY, BookingStatus.CANCELLED}
    ),
    BookingStatus.PENDING_MANUAL_DISPATCH: frozenset(
        {BookingStatus.PROVIDER_ASSIGNED, BookingStatus.CONFIRMED, BookingStatus.NO_CAPACITY, BookingStatus.CANCELLED}
    ),
    BookingStatus.PROVIDER_ASSIGNED: frozenset(
        {BookingStatus.CONFIRMED, BookingStatus.PROVIDER_DECLINED, BookingStatus.REASSIGNMENT_REQUIRED, BookingStatus.CANCELLED}
    ),
    BookingStatus.PROVIDER_DECLINED: frozenset(
        {BookingStatus.REASSIGNMENT_REQUIRED, BookingStatus.CANCELLED}
    ),
    BookingStatus.REASSIGNMENT_REQUIRED: frozenset(
        {BookingStatus.PROVIDER_ASSIGNED, BookingStatus.NO_CAPACITY, BookingStatus.CANCELLED}
    ),
    BookingStatus.CONFIRMED: frozenset(
        {BookingStatus.EN_ROUTE, BookingStatus.RESCHEDULED, BookingStatus.REASSIGNMENT_REQUIRED, BookingStatus.CANCELLED}
    ),
    BookingStatus.RESCHEDULED: frozenset(
        {BookingStatus.CAPACITY_HELD, BookingStatus.AWAITING_ASSIGNMENT, BookingStatus.PENDING_MANUAL_DISPATCH, BookingStatus.CANCELLED}
    ),
    BookingStatus.EN_ROUTE: frozenset({BookingStatus.IN_PROGRESS, BookingStatus.CANCELLED}),
    BookingStatus.IN_PROGRESS: frozenset({BookingStatus.COMPLETED}),
}


def ensure_transition(current: BookingStatus, target: BookingStatus) -> None:
    if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise DomainError(
            "INVALID_STATE_TRANSITION",
            f"Booking cannot move from {current.value} to {target.value}",
            409,
        )
