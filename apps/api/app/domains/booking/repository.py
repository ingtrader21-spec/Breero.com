import uuid
from datetime import UTC, datetime

from geoalchemy2.functions import ST_Covers
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.booking.models import (
    CAPACITY_HOLDING_STATUSES,
    Address,
    AvailabilityRule,
    Booking,
    BookingStatus,
    Customer,
    LegalEntity,
    ProviderServiceCoverage,
    ProviderWorkingHours,
    ServiceArea,
)
from app.domains.geography.models import ServiceZoneOffering
from app.domains.provider_catalog.models import ApprovalStatus, ProviderService
from app.domains.workforce.models import Vendor, VendorStatus, Worker, WorkerStatus


class BookingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def service_area_at(
        self, longitude: float, latitude: float, country_code: str, state_code: str | None,
        city: str, postal_code: str,
    ) -> tuple[ServiceArea, LegalEntity] | None:
        point = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
        stmt = (
            select(ServiceArea, LegalEntity)
            .join(LegalEntity, LegalEntity.id == ServiceArea.legal_entity_id)
            .where(
                ServiceArea.active.is_(True),
                LegalEntity.active.is_(True),
                ServiceArea.country_code == country_code,
                (ServiceArea.state_code.is_(None) | (ServiceArea.state_code == state_code)),
                (ServiceArea.city.is_(None) | (func.lower(ServiceArea.city) == city.lower())),
                (
                    (ServiceArea.postal_codes == [])
                    | ServiceArea.postal_codes.contains([postal_code[:5]])
                ),
                (
                    ServiceArea.boundary.is_(None)
                    | ST_Covers(ServiceArea.boundary, point)
                ),
            )
            .limit(1)
        )
        row = (await self.session.execute(stmt)).first()
        return (row[0], row[1]) if row else None

    async def zone_offering(
        self, service_area_id: uuid.UUID, service_id: uuid.UUID
    ) -> ServiceZoneOffering | None:
        return await self.session.scalar(
            select(ServiceZoneOffering).where(
                ServiceZoneOffering.service_area_id == service_area_id,
                ServiceZoneOffering.service_id == service_id,
            )
        )

    async def add_address(self, address: Address) -> Address:
        self.session.add(address)
        await self.session.flush()
        return address

    async def address(self, address_id: uuid.UUID) -> Address | None:
        return await self.session.get(Address, address_id)

    async def legal_entity_for_area(self, area_id: uuid.UUID) -> LegalEntity | None:
        stmt = select(LegalEntity).join(ServiceArea).where(ServiceArea.id == area_id)
        return await self.session.scalar(stmt)

    async def availability_rules(
        self, service_id: uuid.UUID, area_id: uuid.UUID
    ) -> list[AvailabilityRule]:
        stmt = select(AvailabilityRule).where(
            AvailabilityRule.service_id == service_id,
            AvailabilityRule.service_area_id == area_id,
        )
        return list((await self.session.scalars(stmt)).all())

    async def booking_count(self, service_id: uuid.UUID, start: datetime, end: datetime) -> int:
        now = datetime.now(UTC)
        stmt = select(func.count(Booking.id)).where(
            Booking.service_id == service_id,
            Booking.window_start == start,
            Booking.window_end == end,
            (
                Booking.status == BookingStatus.CONFIRMED
            )
            | (
                Booking.status.in_(CAPACITY_HOLDING_STATUSES)
                & (Booking.expires_at > now)
            ),
        )
        return int(await self.session.scalar(stmt) or 0)

    async def eligible_provider_hours(
        self, service_id: uuid.UUID, postal_code: str, weekday: int
    ) -> list[tuple[Worker, ProviderWorkingHours]]:
        # ProviderServiceCoverage (ops-assigned, per worker/postal code) remains the
        # authoritative fine-grained gate. The outer join to ProviderService adds an
        # opt-in check on top of it: a vendor that has gone through the self-service
        # catalog for this service must be APPROVED and active there too, or their
        # workers are excluded even if ProviderServiceCoverage still lists them.
        # Vendors with no ProviderService row for this service at all (the coverage
        # was assigned directly by ops, without the vendor ever using the catalog)
        # are unaffected -- this only tightens eligibility once a vendor opts into
        # self-service catalog management, it never loosens it and never breaks a
        # vendor that predates the catalog feature.
        stmt = (
            select(Worker, ProviderWorkingHours)
            .join(Vendor, Vendor.id == Worker.vendor_id)
            .join(ProviderServiceCoverage, ProviderServiceCoverage.worker_id == Worker.id)
            .join(ProviderWorkingHours, ProviderWorkingHours.worker_id == Worker.id)
            .outerjoin(
                ProviderService,
                and_(
                    ProviderService.vendor_id == Vendor.id,
                    ProviderService.service_id == service_id,
                ),
            )
            .where(
                Vendor.status == VendorStatus.ACTIVE,
                Worker.status == WorkerStatus.ACTIVE,
                Worker.available.is_(True),
                ProviderServiceCoverage.active.is_(True),
                ProviderServiceCoverage.service_id == service_id,
                ProviderServiceCoverage.postal_code == postal_code[:5],
                ProviderWorkingHours.weekday == weekday,
                or_(
                    ProviderService.id.is_(None),
                    and_(
                        ProviderService.status == ApprovalStatus.APPROVED,
                        ProviderService.active.is_(True),
                    ),
                ),
            )
        )
        return [(row[0], row[1]) for row in (await self.session.execute(stmt)).all()]

    async def provider_booking_count(
        self, worker_id: uuid.UUID, start: datetime, end: datetime
    ) -> int:
        now = datetime.now(UTC)
        stmt = select(func.count(Booking.id)).where(
            Booking.provider_worker_id == worker_id,
            Booking.window_start < end,
            Booking.window_end > start,
            (
                Booking.status == BookingStatus.CONFIRMED
            )
            | (
                Booking.status.in_(CAPACITY_HOLDING_STATUSES)
                & (Booking.expires_at > now)
            ),
        )
        return int(await self.session.scalar(stmt) or 0)

    async def lock_provider_slot(self, worker_id: uuid.UUID, start: datetime) -> None:
        key = f"provider-slot:{worker_id}:{start.isoformat()}"
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": key}
        )

    async def lock_slot(self, service_id: uuid.UUID, start: datetime, end: datetime) -> None:
        """Serialize capacity decisions for one service/window across API processes."""
        key = f"booking-slot:{service_id}:{start.isoformat()}:{end.isoformat()}"
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": key}
        )

    async def lock_idempotency_key(self, key: str) -> None:
        """Serialize lookup/create for one booking idempotency key across API processes."""
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"booking-idempotency:{key}"},
        )

    async def booking_by_idempotency_key(self, key: str) -> Booking | None:
        return await self.session.scalar(select(Booking).where(Booking.idempotency_key == key))

    async def customer_for_email(self, email: str) -> Customer | None:
        return await self.session.scalar(select(Customer).where(Customer.email == email).limit(1))

    async def add(self, instance: object) -> None:
        self.session.add(instance)
        await self.session.flush()

    async def customer_bookings(self, customer_id: uuid.UUID) -> list[Booking]:
        stmt = (
            select(Booking)
            .where(Booking.customer_id == customer_id)
            .order_by(Booking.created_at.desc())
        )
        return list((await self.session.scalars(stmt)).all())
