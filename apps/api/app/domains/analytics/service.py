"""Assemble scoped marketplace metric groups from one read-only snapshot."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import DomainError
from app.domains.analytics.repository import AnalyticsRepository, Window
from app.domains.analytics.schemas import (
    AnalyticsProjectionRead,
    AnalyticsScopeKind,
    AnalyticsScopeRead,
    AnalyticsWindowRead,
    MarketplaceMetricsRead,
    MetricGroupKey,
    MetricGroupRead,
    MetricGroupStatus,
    MetricValueRead,
)
from app.domains.analytics.scope import AnalyticsScope

DEFAULT_WINDOW = timedelta(days=30)
MAX_WINDOW = timedelta(days=366)
MAX_AGE_SECONDS = 300

GROUP_LABELS: dict[MetricGroupKey, str] = {
    MetricGroupKey.request: "Requests",
    MetricGroupKey.qualification: "Qualification",
    MetricGroupKey.matching: "Matching",
    MetricGroupKey.opportunity: "Opportunities",
    MetricGroupKey.quote: "Quotes",
    MetricGroupKey.booking: "Bookings",
    MetricGroupKey.utilization: "Utilization",
    MetricGroupKey.completion: "Completion",
    MetricGroupKey.cancellation: "Cancellation",
    MetricGroupKey.review: "Reviews",
    MetricGroupKey.response_time: "Response time",
    MetricGroupKey.finance: "Finance",
}


def resolve_window(start: datetime | None, end: datetime | None, now: datetime) -> Window:
    for name, value in (("start", start), ("end", end)):
        if value is not None and value.tzinfo is None:
            raise DomainError(
                "INVALID_ANALYTICS_WINDOW",
                "Analytics window bounds must include a timezone offset.",
                422,
                fields={name: "timezone offset required"},
            )
    resolved_end = end or now
    resolved_start = start or resolved_end - DEFAULT_WINDOW
    if resolved_start >= resolved_end:
        raise DomainError(
            "INVALID_ANALYTICS_WINDOW", "Analytics window start must precede its end.", 422
        )
    if resolved_end - resolved_start > MAX_WINDOW:
        raise DomainError(
            "INVALID_ANALYTICS_WINDOW", "Analytics window cannot exceed 366 days.", 422
        )
    return Window(resolved_start.astimezone(UTC), resolved_end.astimezone(UTC))


def _count(key: str, label: str, value: int) -> MetricValueRead:
    return MetricValueRead(key=key, label=label, unit="count", value=int(value))


def _ratio(key: str, label: str, numerator: int, denominator: int) -> MetricValueRead:
    return MetricValueRead(
        key=key,
        label=label,
        unit="ratio",
        value=round(numerator / denominator, 4) if denominator else None,
        numerator=int(numerator),
        denominator=int(denominator),
    )


def _seconds(key: str, label: str, value: Any) -> MetricValueRead:
    return MetricValueRead(
        key=key,
        label=label,
        unit="seconds",
        value=round(float(value), 1) if value is not None else None,
    )


def _available(
    key: MetricGroupKey,
    sources: list[str],
    watermark: datetime | None,
    values: list[MetricValueRead],
    note: str | None = None,
) -> MetricGroupRead:
    return MetricGroupRead(
        key=key,
        label=GROUP_LABELS[key],
        status=MetricGroupStatus.available,
        sources=sources,
        source_watermark=watermark,
        values=values,
        note=note,
    )


def _unavailable(key: MetricGroupKey, reason: str, blocked_by: str | None = None) -> MetricGroupRead:
    return MetricGroupRead(
        key=key,
        label=GROUP_LABELS[key],
        status=MetricGroupStatus.unavailable,
        reason=reason,
        blocked_by=blocked_by,
    )


def _restricted(key: MetricGroupKey, reason: str, sources: list[str]) -> MetricGroupRead:
    return MetricGroupRead(
        key=key,
        label=GROUP_LABELS[key],
        status=MetricGroupStatus.restricted,
        reason=reason,
        sources=sources,
    )


class MarketplaceMetricsService:
    """Read-only projection. Opens its own snapshot session and never writes."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession] | Callable[[], Any]) -> None:
        self.session_factory = session_factory

    async def metrics(
        self,
        scope: AnalyticsScope,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> MarketplaceMetricsRead:
        async with self.session_factory() as session:
            await session.connection(
                execution_options={"isolation_level": "REPEATABLE READ", "postgresql_readonly": True}
            )
            try:
                repository = AnalyticsRepository(session)
                generated_at = await repository.snapshot_time()
                window = resolve_window(start, end, generated_at)
                groups = await self._groups(repository, scope, window)
            finally:
                await session.rollback()
        return MarketplaceMetricsRead(
            scope=AnalyticsScopeRead(kind=scope.kind, vendor_id=scope.vendor_id),
            window=AnalyticsWindowRead(start=window.start, end=window.end),
            generated_at=generated_at,
            projection=AnalyticsProjectionRead(max_age_seconds=MAX_AGE_SECONDS),
            groups=groups,
        )

    async def _groups(
        self, repository: AnalyticsRepository, scope: AnalyticsScope, window: Window
    ) -> list[MetricGroupRead]:
        vendor_id = scope.vendor_id if scope.kind == AnalyticsScopeKind.provider else None
        provider = scope.kind == AnalyticsScopeKind.provider
        jobs = await repository.jobs(window, vendor_id)
        offers = await repository.dispatch_offers(window, vendor_id)
        quotes = await repository.work_requests(window, vendor_id)
        bookings = await repository.bookings(window, vendor_id)

        if provider:
            not_attributable = (
                "Booking intents are anonymous until a provider is assigned, so they "
                "cannot be attributed to a provider organization."
            )
            request = _restricted(MetricGroupKey.request, not_attributable, ["booking_intents"])
            qualification = _restricted(
                MetricGroupKey.qualification, not_attributable, ["booking_intents"]
            )
            matching = _restricted(
                MetricGroupKey.matching,
                "Unmatched jobs have no provider; matching is a marketplace-level metric.",
                ["jobs"],
            )
        else:
            intents = await repository.booking_intents(window)
            request = _available(
                MetricGroupKey.request,
                ["booking_intents"],
                intents["watermark"],
                [
                    _count("intents_created", "Booking intents started", intents["created"]),
                    _count("intents_submitted", "Submitted", intents["submitted"]),
                    _count("intents_expired", "Expired", intents["expired"]),
                    _ratio(
                        "submission_rate", "Submission rate", intents["submitted"], intents["created"]
                    ),
                ],
            )
            qualification = _available(
                MetricGroupKey.qualification,
                ["booking_intents"],
                intents["watermark"],
                [
                    _count("address_validated", "Currently at address validated", intents["address_validated"]),
                    _count("coverage_confirmed", "Currently at coverage confirmed", intents["coverage_confirmed"]),
                    _count("availability_found", "Currently at availability found", intents["availability_found"]),
                    _ratio(
                        "qualification_rate",
                        "Qualified (coverage confirmed or later)",
                        intents["qualified"],
                        intents["created"],
                    ),
                ],
                note=(
                    "Counts reflect each intent's current status. Expired intents are not "
                    "counted as qualified because stage history is not retained."
                ),
            )
            matching = _available(
                MetricGroupKey.matching,
                ["jobs"],
                jobs["watermark"],
                [
                    _count("jobs_created", "Jobs created", jobs["created"]),
                    _count("jobs_awaiting_match", "Awaiting match", jobs["awaiting_match"]),
                    _count("jobs_matched", "Matched to a provider", jobs["matched"]),
                    _ratio("match_rate", "Match rate", jobs["matched"], jobs["created"]),
                ],
            )

        answered = offers["accepted"] + offers["declined"] + offers["expired"]
        decided_quotes = quotes["approved"] + quotes["declined"] + quotes["expired"]
        closed_jobs = jobs["completed"] + jobs["cancelled"]
        return [
            request,
            qualification,
            matching,
            _available(
                MetricGroupKey.opportunity,
                ["dispatch_offers"],
                offers["watermark"],
                [
                    _count("offers_sent", "Offers sent", offers["offered"]),
                    _count("offers_pending", "Pending", offers["pending"]),
                    _count("offers_accepted", "Accepted", offers["accepted"]),
                    _count("offers_declined", "Declined", offers["declined"]),
                    _count("offers_expired", "Expired", offers["expired"]),
                    _ratio("acceptance_rate", "Acceptance rate", offers["accepted"], answered),
                ],
            ),
            _available(
                MetricGroupKey.quote,
                ["work_requests", "jobs"],
                quotes["watermark"],
                [
                    _count("quotes_issued", "Quotes issued", quotes["issued"]),
                    _count("quotes_pending", "Awaiting customer", quotes["pending"]),
                    _count("quotes_approved", "Approved", quotes["approved"]),
                    _count("quotes_declined", "Declined", quotes["declined"]),
                    _ratio("quote_approval_rate", "Approval rate", quotes["approved"], decided_quotes),
                ],
                note="Quote amounts are finance data and are excluded until finance certification.",
            ),
            _available(
                MetricGroupKey.booking,
                ["bookings", "jobs"] if provider else ["bookings"],
                bookings["watermark"],
                [
                    _count("bookings_created", "Bookings created", bookings["created"]),
                    _count("bookings_confirmed", "Confirmed or later", bookings["confirmed"]),
                    _count("bookings_unfulfilled", "No coverage, capacity, or expired", bookings["unfulfilled"]),
                    _ratio(
                        "confirmation_rate", "Confirmation rate", bookings["confirmed"], bookings["created"]
                    ),
                ],
                note="Provider scope includes only bookings whose job is assigned to the provider."
                if provider
                else None,
            ),
            _unavailable(
                MetricGroupKey.utilization,
                "No capacity-minutes projection exists in the source of record; utilization "
                "is withheld rather than estimated.",
            ),
            _available(
                MetricGroupKey.completion,
                ["jobs"],
                jobs["watermark"],
                [
                    _count("jobs_completed", "Jobs completed", jobs["completed"]),
                    _count("jobs_cancelled", "Jobs cancelled", jobs["cancelled"]),
                    _ratio("completion_rate", "Completion rate of closed jobs", jobs["completed"], closed_jobs),
                ],
            ),
            _available(
                MetricGroupKey.cancellation,
                ["bookings"],
                bookings["watermark"],
                [
                    _count("bookings_cancelled", "Bookings cancelled", bookings["cancelled"]),
                    _ratio(
                        "cancellation_rate", "Cancellation rate", bookings["cancelled"], bookings["created"]
                    ),
                ],
            ),
            _unavailable(
                MetricGroupKey.review,
                "No review source of record exists yet.",
                blocked_by="PAS-128",
            ),
            _available(
                MetricGroupKey.response_time,
                ["dispatch_offers"],
                offers["watermark"],
                [
                    _count("offers_responded", "Offers answered", offers["responded"]),
                    _seconds("median_response_seconds", "Median response time", offers["median_seconds"]),
                    _seconds("p90_response_seconds", "90th percentile response time", offers["p90_seconds"]),
                ],
                note="Measured from offer creation to provider accept or decline.",
            ),
            _unavailable(
                MetricGroupKey.finance,
                "Payment, ledger, earnings, and payout metrics require certified finance "
                "projections and stay withheld until then.",
                blocked_by="PAS-129",
            ),
        ]
