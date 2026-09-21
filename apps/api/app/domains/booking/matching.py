import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time

from geoalchemy2 import Geography
from sqlalchemy import and_, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.domains.administration.models import OperatingHour
from app.domains.booking.capacity import CapacityLimit, CapacityUsage, ensure_capacity
from app.domains.booking.capacity_models import (
    BookingCapacityHold,
    CapacityHoldStatus,
    ProviderAvailabilityException,
    ProviderAvailabilityRule,
    ProviderCapacityRule,
)
from app.domains.booking.models import Address, Booking, BookingStatus
from app.domains.booking.timezones import enforce_breero_hours, timezone
from app.domains.catalog.models import Service
from app.domains.jobs.models import Job, JobStatus
from app.domains.workforce.models import (
    ProviderCredential,
    ProviderCredentialType,
    Vendor,
    VendorStatus,
    Worker,
    WorkerStatus,
)
from app.domains.workforce.provider_models import ProviderService, ProviderServiceArea


@dataclass(frozen=True)
class ProviderCandidate:
    provider_id: uuid.UUID
    professional_id: uuid.UUID
    score: int
    distance_meters: int | None
    available_capacity_minutes: int
    schedule_match: bool
    service_area_match: bool
    warnings: tuple[str, ...]
    capacity_minutes: int


class ProviderMatcher:
    """Indexed candidate filtering; ranking details never leave authorized admin APIs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def candidates(
        self,
        service: Service,
        address: Address,
        start_utc: datetime,
        end_utc: datetime,
        *,
        emergency: bool = False,
        professional_id: uuid.UUID | None = None,
    ) -> list[ProviderCandidate]:
        zone = timezone(address.timezone_name)
        local_start, local_end = start_utc.astimezone(zone), end_utc.astimezone(zone)
        base = (
            select(Worker, Vendor)
            .join(Vendor, Vendor.id == Worker.vendor_id)
            .join(ProviderService, ProviderService.provider_id == Vendor.id)
            .join(ProviderServiceArea, ProviderServiceArea.provider_id == Vendor.id)
            .where(
                ProviderService.service_id == service.id,
                ProviderService.active.is_(True),
                ProviderService.approval_status == "APPROVED",
                ProviderServiceArea.postal_code == address.postal_code[:5],
                ProviderServiceArea.active.is_(True),
                ProviderServiceArea.approval_status == "APPROVED",
                Vendor.status == VendorStatus.ACTIVE,
                Vendor.compliance_status == "APPROVED",
                Worker.status == WorkerStatus.ACTIVE,
                Worker.available.is_(True),
            )
            .distinct(Worker.id, Vendor.id)
            .limit(250)
        )
        if professional_id:
            base = base.where(Worker.id == professional_id)
        rows = (await self.session.execute(base)).all()
        results: list[ProviderCandidate] = []
        for worker, vendor in rows:
            if local_start.weekday() == 6 and not worker.sunday_emergency_enabled:
                continue
            try:
                operating_hour = await self.session.get(OperatingHour, local_start.weekday())
                if operating_hour and not operating_hour.active:
                    continue
                enforce_breero_hours(
                    local_start,
                    local_end,
                    service_emergency_eligible=bool(service.emergency_eligible),
                    provider_sunday_emergency_enabled=worker.sunday_emergency_enabled,
                    open_local=operating_hour.start_local_time if operating_hour else time(7),
                    close_local=operating_hour.end_local_time if operating_hour else time(19),
                    emergency_only=operating_hour.emergency_only if operating_hour else None,
                )
            except DomainError:
                continue
            if not await self._schedule_matches(worker.id, local_start, local_end, emergency):
                continue
            if not await self._credentials_valid(vendor.id, address.state_code, local_start.date()):
                continue
            distance = await self.session.scalar(
                select(
                    func.ST_Distance(Vendor.home_location, cast(Address.location, Geography))
                )
                .select_from(Vendor)
                .join(Address, Address.id == address.id)
                .where(Vendor.id == vendor.id)
            )
            distance_meters = round(float(distance)) if distance is not None else None
            travel_minutes = round(distance_meters / 500) if distance_meters is not None else 0
            service_minutes = service.duration_minutes or 60
            capacity_minutes = (
                service_minutes
                + service.before_buffer_minutes
                + service.after_buffer_minutes
                + travel_minutes
            )
            limit = await self._limit(vendor.id, worker, local_start.date())
            usage, overlaps = await self._usage(worker.id, local_start.date(), start_utc, end_utc, zone)
            try:
                current = ensure_capacity(
                    limit,
                    usage,
                    capacity_minutes,
                    overlapping_jobs=overlaps,
                    emergency=emergency,
                )
            except DomainError:
                continue
            capacity_score = min(10, round(current.remaining_minutes / max(limit.max_minutes, 1) * 10))
            distance_score = (
                max(0, 25 - round(distance_meters / 4_000))
                if distance_meters is not None
                else 0
            )
            score = 30 + distance_score + 15 + capacity_score
            results.append(
                ProviderCandidate(
                    provider_id=vendor.id,
                    professional_id=worker.id,
                    score=score,
                    distance_meters=distance_meters,
                    available_capacity_minutes=current.remaining_minutes,
                    schedule_match=True,
                    service_area_match=True,
                    warnings=("distance_unavailable",) if distance_meters is None else (),
                    capacity_minutes=capacity_minutes,
                )
            )
        return sorted(results, key=lambda candidate: (-candidate.score, str(candidate.professional_id)))

    async def _schedule_matches(
        self, worker_id: uuid.UUID, start: datetime, end: datetime, emergency: bool
    ) -> bool:
        statement = select(ProviderAvailabilityRule).where(
                ProviderAvailabilityRule.provider_professional_id == worker_id,
                ProviderAvailabilityRule.day_of_week == start.weekday(),
                ProviderAvailabilityRule.available.is_(True),
                ProviderAvailabilityRule.start_local_time <= start.time(),
                ProviderAvailabilityRule.end_local_time >= end.time(),
            )
        if not emergency:
            statement = statement.where(ProviderAvailabilityRule.emergency_only.is_(False))
        rule = await self.session.scalar(statement)
        if not rule:
            return False
        exception = await self.session.scalar(
            select(ProviderAvailabilityException.id).where(
                ProviderAvailabilityException.provider_professional_id == worker_id,
                ProviderAvailabilityException.status == "ACTIVE",
                ProviderAvailabilityException.start_at < end.astimezone(UTC),
                ProviderAvailabilityException.end_at > start.astimezone(UTC),
            )
        )
        return exception is None

    async def _credentials_valid(self, vendor_id: uuid.UUID, state: str | None, on_date: date) -> bool:
        if not state:
            return False
        values = set(
            (
                await self.session.scalars(
                    select(ProviderCredential.credential_type).where(
                        ProviderCredential.vendor_id == vendor_id,
                        ProviderCredential.jurisdiction.in_([state, "US"]),
                        ProviderCredential.verified.is_(True),
                        ProviderCredential.expires_on >= on_date,
                    )
                )
            ).all()
        )
        return {ProviderCredentialType.LICENSE, ProviderCredentialType.INSURANCE}.issubset(values)

    async def _limit(self, vendor_id: uuid.UUID, worker: Worker, on_date: date) -> CapacityLimit:
        rule = await self.session.scalar(
            select(ProviderCapacityRule)
            .where(
                ProviderCapacityRule.provider_id == vendor_id,
                (ProviderCapacityRule.professional_id.is_(None) | (ProviderCapacityRule.professional_id == worker.id)),
                ProviderCapacityRule.effective_from <= on_date,
                (ProviderCapacityRule.effective_until.is_(None) | (ProviderCapacityRule.effective_until >= on_date)),
            )
            .order_by(ProviderCapacityRule.professional_id.desc().nullslast(), ProviderCapacityRule.effective_from.desc())
        )
        return CapacityLimit(
            max_jobs=rule.max_jobs_daily if rule else worker.maximum_jobs_per_day,
            max_minutes=rule.max_minutes_daily if rule else worker.maximum_minutes_per_day,
            max_concurrent_jobs=rule.max_concurrent_jobs if rule else 1,
            emergency_reserved_jobs=rule.emergency_reserved_jobs if rule else 0,
            emergency_reserved_minutes=rule.emergency_reserved_minutes if rule else 0,
        )

    async def _usage(self, worker_id: uuid.UUID, local_date: date, start: datetime, end: datetime, zone) -> tuple[CapacityUsage, int]:
        day_start = datetime.combine(local_date, datetime.min.time(), tzinfo=zone).astimezone(UTC)
        day_end = datetime.combine(local_date, datetime.max.time(), tzinfo=zone).astimezone(UTC)
        jobs = list(
            (
                await self.session.scalars(
                    select(Job).where(
                        Job.worker_id == worker_id,
                        Job.scheduled_start < day_end,
                        Job.scheduled_end > day_start,
                        Job.status.not_in([JobStatus.CANCELLED, JobStatus.COMPLETED]),
                    )
                )
            ).all()
        )
        now = datetime.now(UTC)
        holds = list(
            (
                await self.session.scalars(
                    select(BookingCapacityHold).where(
                        BookingCapacityHold.professional_candidate_id == worker_id,
                        or_(
                            and_(
                                BookingCapacityHold.status == CapacityHoldStatus.HELD,
                                BookingCapacityHold.expires_at > now,
                            ),
                            and_(
                                BookingCapacityHold.status == CapacityHoldStatus.CONVERTED,
                                select(Booking.id).where(
                                    Booking.id == BookingCapacityHold.booking_id,
                                    Booking.status.not_in([
                                        BookingStatus.CANCELLED, BookingStatus.EXPIRED,
                                        BookingStatus.COMPLETED,
                                    ]),
                                ).exists(),
                                ~select(Job.id).where(
                                    Job.booking_id == BookingCapacityHold.booking_id,
                                ).exists(),
                            ),
                        ),
                        BookingCapacityHold.slot_start_utc < day_end,
                        BookingCapacityHold.slot_end_utc > day_start,
                    )
                )
            ).all()
        )
        booking_minutes = sum(
            max(round((job.scheduled_end - job.scheduled_start).total_seconds() / 60), 0)
            for job in jobs
        )
        hold_minutes = sum(hold.capacity_minutes for hold in holds)
        overlaps = sum(job.scheduled_start < end and job.scheduled_end > start for job in jobs)
        overlaps += sum(hold.slot_start_utc < end and hold.slot_end_utc > start for hold in holds)
        return CapacityUsage(
            job_count=len(jobs),
            booking_minutes=booking_minutes,
            hold_count=len(holds),
            hold_minutes=hold_minutes,
        ), overlaps
