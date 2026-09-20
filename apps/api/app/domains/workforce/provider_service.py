import uuid
from datetime import UTC, date, datetime, time, timedelta

from geoalchemy2.elements import WKTElement
from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.domains.auth.models import User, UserRole
from app.domains.booking.capacity_models import (
    AvailabilityExceptionReason,
    BookingCapacityHold,
    CapacityHoldStatus,
    ProviderAvailabilityException,
    ProviderAvailabilityRule,
    ProviderCapacityRule,
)
from app.domains.booking.timezones import timezone
from app.domains.catalog.models import Service
from app.domains.common.outbox import AuditLog
from app.domains.jobs.models import Job
from app.domains.workforce.models import Vendor, Worker
from app.domains.workforce.provider_models import ProviderService, ProviderServiceArea
from app.domains.workforce.provider_schemas import (
    AvailabilityExceptionPatch,
    AvailabilityExceptionWrite,
    AvailabilityRuleWrite,
    CapacityDay,
    CapacityRuleWrite,
    ProviderServiceAreaWrite,
)


class ProviderPortalService:
    def __init__(self, session: AsyncSession, user: User) -> None:
        self.session = session
        self.user = user

    async def context(self) -> tuple[Vendor, Worker | None]:
        if self.user.role == UserRole.vendor_admin:
            vendor = await self.session.scalar(
                select(Vendor).where(Vendor.owner_user_id == self.user.id)
            )
            worker = await self.session.scalar(select(Worker).where(Worker.user_id == self.user.id))
        elif self.user.role == UserRole.technician:
            worker = await self.session.scalar(select(Worker).where(Worker.user_id == self.user.id))
            vendor = await self.session.get(Vendor, worker.vendor_id) if worker else None
        else:
            vendor, worker = None, None
        if not vendor:
            raise DomainError("FORBIDDEN", "Account is not linked to a provider", 403)
        return vendor, worker

    async def jobs(self) -> list[Job]:
        vendor, worker = await self.context()
        statement = select(Job).where(Job.vendor_id == vendor.id)
        if self.user.role == UserRole.technician:
            if worker is None:
                raise DomainError("FORBIDDEN", "Account is not linked to a professional", 403)
            statement = statement.where(Job.worker_id == worker.id)
        return list((await self.session.scalars(statement.order_by(Job.scheduled_start))).all())

    async def job(self, job_id: uuid.UUID) -> Job:
        jobs = await self.jobs()
        job = next((item for item in jobs if item.id == job_id), None)
        if not job:
            raise DomainError("FORBIDDEN", "Job is not assigned to this provider account", 403)
        return job

    async def services(self) -> list[ProviderService]:
        vendor, _ = await self.context()
        return list(
            (
                await self.session.scalars(
                    select(ProviderService).where(ProviderService.provider_id == vendor.id)
                )
            ).all()
        )

    async def add_service(self, service_id: uuid.UUID) -> ProviderService:
        vendor, _ = await self.context()
        if not await self.session.get(Service, service_id):
            raise DomainError("SERVICE_NOT_FOUND", "BREERO catalog service not found", 404)
        item = ProviderService(
            provider_id=vendor.id,
            service_id=service_id,
            active=False,
            approval_status="PENDING",
        )
        self.session.add(item)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            raise DomainError("SERVICE_ALREADY_SELECTED", "Provider service already exists", 409) from exc
        self._audit("provider.service.requested", "provider_service", item.id)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def remove_service(self, item_id: uuid.UUID) -> None:
        item = await self._owned(ProviderService, item_id)
        item.active = False
        item.approval_status = "REMOVAL_PENDING"
        self._audit("provider.service.removal_requested", "provider_service", item.id)
        await self.session.commit()

    async def change_service(self, item_id: uuid.UUID, requested_active: bool) -> ProviderService:
        item = await self._owned(ProviderService, item_id)
        item.active = False if requested_active else item.active
        item.approval_status = "PENDING" if requested_active else "REMOVAL_PENDING"
        self._audit("provider.service.change_requested", "provider_service", item.id)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def areas(self) -> list[ProviderServiceArea]:
        vendor, _ = await self.context()
        return list(
            (
                await self.session.scalars(
                    select(ProviderServiceArea).where(ProviderServiceArea.provider_id == vendor.id)
                )
            ).all()
        )

    async def add_area(self, data: ProviderServiceAreaWrite) -> ProviderServiceArea:
        vendor, _ = await self.context()
        if data.professional_id:
            await self._owned_worker(data.professional_id, vendor.id)
        center = None
        if data.latitude is not None and data.longitude is not None:
            center = WKTElement(f"POINT({data.longitude} {data.latitude})", srid=4326)
        item = ProviderServiceArea(
            provider_id=vendor.id,
            **data.model_dump(exclude={"latitude", "longitude", "state"}),
            state=data.state.upper() if data.state else None,
            center=center,
            active=False,
            approval_status="PENDING",
        )
        self.session.add(item)
        await self.session.flush()
        self._audit("provider.service_area.requested", "provider_service_area", item.id)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def update_area(self, item_id: uuid.UUID, data: ProviderServiceAreaWrite) -> ProviderServiceArea:
        item = await self._owned(ProviderServiceArea, item_id)
        vendor, _ = await self.context()
        if data.professional_id:
            await self._owned_worker(data.professional_id, vendor.id)
        values = data.model_dump(exclude={"latitude", "longitude"})
        for name, value in values.items():
            setattr(item, name, value)
        item.center = (
            WKTElement(f"POINT({data.longitude} {data.latitude})", srid=4326)
            if data.latitude is not None and data.longitude is not None
            else None
        )
        item.active = False
        item.approval_status = "PENDING"
        self._audit("provider.service_area.changed", "provider_service_area", item.id)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def remove_area(self, item_id: uuid.UUID) -> None:
        item = await self._owned(ProviderServiceArea, item_id)
        item.active = False
        item.approval_status = "REMOVAL_PENDING"
        self._audit("provider.service_area.removal_requested", "provider_service_area", item.id)
        await self.session.commit()

    async def availability(self) -> list[ProviderAvailabilityRule]:
        vendor, _ = await self.context()
        return list(
            (
                await self.session.scalars(
                    select(ProviderAvailabilityRule)
                    .join(Worker, Worker.id == ProviderAvailabilityRule.provider_professional_id)
                    .where(Worker.vendor_id == vendor.id)
                    .order_by(ProviderAvailabilityRule.day_of_week, ProviderAvailabilityRule.start_local_time)
                )
            ).all()
        )

    async def replace_availability(self, rules: list[AvailabilityRuleWrite]) -> list[ProviderAvailabilityRule]:
        vendor, _ = await self.context()
        professional_ids = {rule.professional_id for rule in rules}
        for professional_id in professional_ids:
            await self._owned_worker(professional_id, vendor.id)
        for rule in rules:
            timezone(rule.timezone_id)
        await self.session.execute(
            delete(ProviderAvailabilityRule).where(
                ProviderAvailabilityRule.provider_professional_id.in_(
                    select(Worker.id).where(Worker.vendor_id == vendor.id)
                )
            )
        )
        records = [
            ProviderAvailabilityRule(
                provider_professional_id=rule.professional_id,
                **rule.model_dump(exclude={"professional_id"}),
            )
            for rule in rules
        ]
        self.session.add_all(records)
        self._audit("provider.availability.replaced", "vendor", vendor.id, {"rule_count": len(records)})
        await self.session.commit()
        return records

    async def exceptions(self) -> list[ProviderAvailabilityException]:
        vendor, _ = await self.context()
        return list(
            (
                await self.session.scalars(
                    select(ProviderAvailabilityException)
                    .join(Worker, Worker.id == ProviderAvailabilityException.provider_professional_id)
                    .where(Worker.vendor_id == vendor.id)
                    .order_by(ProviderAvailabilityException.start_at)
                )
            ).all()
        )

    async def add_exception(self, data: AvailabilityExceptionWrite) -> ProviderAvailabilityException:
        vendor, _ = await self.context()
        await self._owned_worker(data.professional_id, vendor.id)
        timezone(data.timezone_id)
        item = ProviderAvailabilityException(
            provider_professional_id=data.professional_id,
            start_at=data.start_at.astimezone(UTC),
            end_at=data.end_at.astimezone(UTC),
            timezone_id=data.timezone_id,
            reason=AvailabilityExceptionReason(data.reason),
            status="ACTIVE",
            created_by=self.user.id,
        )
        self.session.add(item)
        await self.session.flush()
        self._audit("provider.availability_exception.created", "availability_exception", item.id)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def update_exception(
        self, item_id: uuid.UUID, data: AvailabilityExceptionPatch
    ) -> ProviderAvailabilityException:
        vendor, _ = await self.context()
        item = await self.session.scalar(
            select(ProviderAvailabilityException)
            .join(Worker, Worker.id == ProviderAvailabilityException.provider_professional_id)
            .where(ProviderAvailabilityException.id == item_id, Worker.vendor_id == vendor.id)
        )
        if not item:
            raise DomainError("FORBIDDEN", "Availability exception is outside this provider", 403)
        start_at = data.start_at or item.start_at
        end_at = data.end_at or item.end_at
        if end_at <= start_at:
            raise DomainError(
                "INVALID_AVAILABILITY_EXCEPTION",
                "Availability exception end must follow start",
                422,
            )
        if data.timezone_id is not None:
            timezone(data.timezone_id)
            item.timezone_id = data.timezone_id
        item.start_at = start_at.astimezone(UTC)
        item.end_at = end_at.astimezone(UTC)
        if data.reason is not None:
            item.reason = AvailabilityExceptionReason(data.reason)
        self._audit("provider.availability_exception.changed", "availability_exception", item.id)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def remove_exception(self, item_id: uuid.UUID) -> None:
        vendor, _ = await self.context()
        item = await self.session.scalar(
            select(ProviderAvailabilityException)
            .join(Worker, Worker.id == ProviderAvailabilityException.provider_professional_id)
            .where(ProviderAvailabilityException.id == item_id, Worker.vendor_id == vendor.id)
        )
        if not item:
            raise DomainError("FORBIDDEN", "Availability exception is outside this provider", 403)
        item.status = "CANCELLED"
        self._audit("provider.availability_exception.cancelled", "availability_exception", item.id)
        await self.session.commit()

    async def capacity(self) -> list[ProviderCapacityRule]:
        vendor, _ = await self.context()
        return list(
            (
                await self.session.scalars(
                    select(ProviderCapacityRule).where(ProviderCapacityRule.provider_id == vendor.id)
                )
            ).all()
        )

    async def set_capacity(self, data: CapacityRuleWrite) -> ProviderCapacityRule:
        vendor, _ = await self.context()
        if data.professional_id:
            await self._owned_worker(data.professional_id, vendor.id)
        item = ProviderCapacityRule(provider_id=vendor.id, **data.model_dump())
        self.session.add(item)
        await self.session.flush()
        self._audit("provider.capacity.changed", "provider_capacity_rule", item.id)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def capacity_calendar(self, start: date, days: int) -> list[CapacityDay]:
        vendor, _ = await self.context()
        end = start + timedelta(days=days)
        start_at = datetime.combine(start, time.min, tzinfo=UTC)
        end_at = datetime.combine(end, time.min, tzinfo=UTC)
        rules = list(
            (
                await self.session.scalars(
                    select(ProviderCapacityRule)
                    .where(
                        ProviderCapacityRule.provider_id == vendor.id,
                        ProviderCapacityRule.effective_from < end,
                        or_(
                            ProviderCapacityRule.effective_until.is_(None),
                            ProviderCapacityRule.effective_until >= start,
                        ),
                    )
                    .order_by(ProviderCapacityRule.effective_from.desc())
                )
            ).all()
        )
        jobs = list(
            (
                await self.session.scalars(
                    select(Job).where(
                        Job.vendor_id == vendor.id,
                        Job.scheduled_start >= start_at,
                        Job.scheduled_start < end_at,
                        Job.status != "CANCELLED",
                    )
                )
            ).all()
        )
        professional_ids = {rule.professional_id for rule in rules if rule.professional_id}
        holds = (
            list(
                (
                    await self.session.scalars(
                        select(BookingCapacityHold).where(
                            BookingCapacityHold.provider_candidate_id == vendor.id,
                            BookingCapacityHold.professional_candidate_id.in_(professional_ids),
                            BookingCapacityHold.slot_start_utc >= start_at,
                            BookingCapacityHold.slot_start_utc < end_at,
                            BookingCapacityHold.status == CapacityHoldStatus.HELD,
                            BookingCapacityHold.expires_at > datetime.now(UTC),
                        )
                    )
                ).all()
            )
            if professional_ids
            else []
        )
        result: list[CapacityDay] = []
        for offset in range(days):
            day = start + timedelta(days=offset)
            active_rules = [
                rule
                for rule in rules
                if rule.effective_from <= day
                and (rule.effective_until is None or rule.effective_until >= day)
            ]
            total_minutes = sum(rule.max_minutes_daily for rule in active_rules)
            max_jobs = sum(rule.max_jobs_daily for rule in active_rules)
            day_jobs = [job for job in jobs if job.scheduled_start.date() == day]
            booking_minutes = sum(
                max(int((job.scheduled_end - job.scheduled_start).total_seconds() // 60), 0)
                for job in day_jobs
            )
            day_holds = [hold for hold in holds if hold.slot_start_utc.date() == day]
            hold_minutes = sum(hold.capacity_minutes for hold in day_holds)
            reserved_minutes = booking_minutes + hold_minutes
            result.append(
                CapacityDay(
                    date=day,
                    total_minutes=total_minutes,
                    reserved_minutes=reserved_minutes,
                    booking_minutes=booking_minutes,
                    buffer_minutes=hold_minutes,
                    remaining_minutes=max(total_minutes - reserved_minutes, 0),
                    job_count=len(day_jobs) + len(day_holds),
                    max_job_count=max_jobs,
                )
            )
        return result

    async def _owned(self, model, item_id: uuid.UUID):
        vendor, _ = await self.context()
        item = await self.session.scalar(
            select(model).where(model.id == item_id, model.provider_id == vendor.id)
        )
        if not item:
            raise DomainError("FORBIDDEN", "Resource is outside this provider", 403)
        return item

    async def _owned_worker(self, worker_id: uuid.UUID, vendor_id: uuid.UUID) -> Worker:
        worker = await self.session.scalar(
            select(Worker).where(Worker.id == worker_id, Worker.vendor_id == vendor_id)
        )
        if not worker:
            raise DomainError("FORBIDDEN", "Professional is outside this provider", 403)
        return worker

    def _audit(
        self,
        action: str,
        resource_type: str,
        resource_id: uuid.UUID,
        metadata: dict | None = None,
    ) -> None:
        self.session.add(
            AuditLog(
                actor_id=self.user.id,
                actor_type="user",
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                metadata_json=metadata or {},
                created_at=datetime.now(UTC),
            )
        )
