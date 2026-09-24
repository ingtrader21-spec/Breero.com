"""Aggregate reads over source-of-record tables. No writes, no caching."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, Select, and_, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.booking.models import Booking, BookingStatus
from app.domains.booking_intents.models import BookingIntent, BookingIntentStatus
from app.domains.dispatch.models import DispatchOffer, OfferStatus
from app.domains.jobs.models import Job, JobStatus, WorkRequest, WorkRequestStatus

CONFIRMED_BOOKING_STATUSES = (
    BookingStatus.CONFIRMED,
    BookingStatus.EN_ROUTE,
    BookingStatus.IN_PROGRESS,
    BookingStatus.COMPLETED,
)
UNFULFILLED_BOOKING_STATUSES = (
    BookingStatus.NO_COVERAGE,
    BookingStatus.NO_CAPACITY,
    BookingStatus.EXPIRED,
)
QUALIFIED_INTENT_STATUSES = (
    BookingIntentStatus.COVERAGE_CONFIRMED,
    BookingIntentStatus.AVAILABILITY_FOUND,
    BookingIntentStatus.SUBMITTED,
)
AWAITING_MATCH_JOB_STATUSES = (JobStatus.CREATED, JobStatus.MATCHING, JobStatus.OFFERED)
MATCHED_JOB_STATUSES = (
    JobStatus.ASSIGNED,
    JobStatus.EN_ROUTE,
    JobStatus.ON_SITE,
    JobStatus.DIAGNOSING,
    JobStatus.AWAITING_APPROVAL,
    JobStatus.IN_PROGRESS,
    JobStatus.COMPLETED,
)
PENDING_QUOTE_STATUSES = (WorkRequestStatus.SUBMITTED, WorkRequestStatus.PENDING_CUSTOMER)
APPROVED_QUOTE_STATUSES = (
    WorkRequestStatus.APPROVED_PENDING_PAYMENT,
    WorkRequestStatus.APPROVED,
    WorkRequestStatus.PAID,
)


@dataclass(frozen=True, slots=True)
class Window:
    start: datetime
    end: datetime

    def contains(self, column: Any) -> ColumnElement[bool]:
        return and_(column >= self.start, column < self.end)


def _count(condition: ColumnElement[bool] | None = None) -> Any:
    return func.count() if condition is None else func.count().filter(condition)


class AnalyticsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _row(self, query: Select[Any]) -> dict[str, Any]:
        return dict((await self.session.execute(query)).mappings().one())

    async def snapshot_time(self) -> datetime:
        value = await self.session.scalar(select(func.now()))
        assert value is not None
        return value

    async def booking_intents(self, window: Window) -> dict[str, Any]:
        status = BookingIntent.status
        return await self._row(
            select(
                _count().label("created"),
                _count(status == BookingIntentStatus.SUBMITTED).label("submitted"),
                _count(status == BookingIntentStatus.EXPIRED).label("expired"),
                _count(status == BookingIntentStatus.ADDRESS_VALIDATED).label("address_validated"),
                _count(status == BookingIntentStatus.COVERAGE_CONFIRMED).label("coverage_confirmed"),
                _count(status == BookingIntentStatus.AVAILABILITY_FOUND).label("availability_found"),
                _count(status.in_(QUALIFIED_INTENT_STATUSES)).label("qualified"),
                func.max(BookingIntent.updated_at).label("watermark"),
            ).where(window.contains(BookingIntent.created_at))
        )

    async def jobs(self, window: Window, vendor_id: uuid.UUID | None) -> dict[str, Any]:
        status = Job.status
        query = select(
            _count().label("created"),
            _count(status.in_(AWAITING_MATCH_JOB_STATUSES)).label("awaiting_match"),
            _count(status.in_(MATCHED_JOB_STATUSES)).label("matched"),
            _count(status == JobStatus.COMPLETED).label("completed"),
            _count(status == JobStatus.CANCELLED).label("cancelled"),
            func.max(Job.updated_at).label("watermark"),
        ).where(window.contains(Job.created_at))
        if vendor_id is not None:
            query = query.where(Job.vendor_id == vendor_id)
        return await self._row(query)

    async def dispatch_offers(self, window: Window, vendor_id: uuid.UUID | None) -> dict[str, Any]:
        status = DispatchOffer.status
        responded = and_(
            DispatchOffer.responded_at.is_not(None),
            status.in_((OfferStatus.ACCEPTED, OfferStatus.DECLINED)),
        )
        latency = func.extract("epoch", DispatchOffer.responded_at - DispatchOffer.created_at)
        query = select(
            _count().label("offered"),
            _count(status == OfferStatus.PENDING).label("pending"),
            _count(status == OfferStatus.ACCEPTED).label("accepted"),
            _count(status == OfferStatus.DECLINED).label("declined"),
            _count(status == OfferStatus.EXPIRED).label("expired"),
            _count(status == OfferStatus.WITHDRAWN).label("withdrawn"),
            _count(responded).label("responded"),
            func.percentile_cont(0.5).within_group(latency).filter(responded).label("median_seconds"),
            func.percentile_cont(0.9).within_group(latency).filter(responded).label("p90_seconds"),
            func.max(
                func.greatest(DispatchOffer.created_at, func.coalesce(DispatchOffer.responded_at, DispatchOffer.created_at))
            ).label("watermark"),
        ).where(window.contains(DispatchOffer.created_at))
        if vendor_id is not None:
            query = query.where(DispatchOffer.vendor_id == vendor_id)
        return await self._row(query)

    async def work_requests(self, window: Window, vendor_id: uuid.UUID | None) -> dict[str, Any]:
        status = WorkRequest.status
        query = (
            select(
                _count(status != WorkRequestStatus.DRAFT).label("issued"),
                _count(status.in_(PENDING_QUOTE_STATUSES)).label("pending"),
                _count(status.in_(APPROVED_QUOTE_STATUSES)).label("approved"),
                _count(status == WorkRequestStatus.DECLINED).label("declined"),
                _count(status == WorkRequestStatus.EXPIRED).label("expired"),
                func.max(WorkRequest.updated_at).label("watermark"),
            )
            .select_from(WorkRequest)
            .join(Job, Job.id == WorkRequest.job_id)
            .where(window.contains(WorkRequest.created_at))
        )
        if vendor_id is not None:
            query = query.where(Job.vendor_id == vendor_id)
        return await self._row(query)

    async def bookings(self, window: Window, vendor_id: uuid.UUID | None) -> dict[str, Any]:
        status = Booking.status
        query = select(
            _count().label("created"),
            _count(status.in_(CONFIRMED_BOOKING_STATUSES)).label("confirmed"),
            _count(status == BookingStatus.COMPLETED).label("completed"),
            _count(status.in_(UNFULFILLED_BOOKING_STATUSES)).label("unfulfilled"),
            _count(status == BookingStatus.CANCELLED).label("cancelled"),
            func.max(Booking.updated_at).label("watermark"),
        ).where(window.contains(Booking.created_at))
        if vendor_id is not None:
            query = query.where(
                exists().where(Job.booking_id == Booking.id, Job.vendor_id == vendor_id)
            )
        return await self._row(query)
