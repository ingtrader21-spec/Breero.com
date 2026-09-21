import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from geoalchemy2.elements import WKTElement

from app.db.session import SessionLocal
from app.domains.booking.capacity_models import ServiceZone
from app.domains.booking.models import (
    Address,
    Booking,
    BookingStatus,
    Customer,
    LegalEntity,
    ServiceArea,
)
from app.domains.catalog.models import Service
from app.workers.tasks import expire_booking_holds


@pytest.mark.asyncio
async def test_expiry_worker_transitions_expired_holds_and_is_idempotent() -> None:
    marker = uuid.uuid4().hex
    now = datetime.now(UTC)
    window_start = now + timedelta(days=2)

    async with SessionLocal() as session:
        # Register the migration-018 service-zone table that Address.service_zone_id references.
        assert ServiceZone.__table__.name == "service_zones"
        entity = LegalEntity(code=f"EXP-{marker[:8]}", name="Expiry Test", currency="USD")
        service = Service(
            slug=f"expiry-worker-{marker}",
            name="Expiry worker test",
            category="home-services",
            pricing_model="quote_required",
            is_active=True,
            is_bookable=True,
        )
        customer = Customer(
            first_name="Expiry",
            last_name="Worker",
            email=f"expiry-{marker}@example.com",
            phone="+12815550111",
        )
        session.add_all([entity, service, customer])
        await session.flush()

        area = ServiceArea(
            legal_entity_id=entity.id,
            name="Expiry test area",
            country_code="US",
            state_code="TX",
            city="Cypress",
            postal_codes=["77433"],
            boundary=WKTElement(
                "MULTIPOLYGON(((-95.8 29.8,-95.5 29.8,-95.5 30.1,-95.8 30.1,-95.8 29.8)))",
                srid=4326,
            ),
            active=True,
        )
        session.add(area)
        await session.flush()

        address = Address(
            formatted_address="20633 Longenbaugh Rd, Cypress, TX 77433",
            line1="20633 Longenbaugh Rd",
            city="Cypress",
            state_code="TX",
            postal_code="77433",
            country_code="US",
            location=WKTElement("POINT(-95.7 29.9)", srid=4326),
            service_area_id=area.id,
            geocoding_provider="expiry-test",
            timezone_name="America/Chicago",
            customer_id=customer.id,
        )
        session.add(address)
        await session.flush()

        def make_booking(status: BookingStatus, expires_at: datetime, suffix: str) -> Booking:
            return Booking(
                reference=f"EX-{marker[:8]}-{suffix}",
                idempotency_key=f"expiry-worker-{marker}-{suffix}",
                idempotency_request_hash=(marker + suffix).ljust(64, "0")[:64],
                customer_id=customer.id,
                address_id=address.id,
                legal_entity_id=entity.id,
                service_id=service.id,
                provider_worker_id=None,
                window_start=window_start,
                window_end=window_start + timedelta(hours=1),
                status=status,
                pricing_snapshot={"expiry_worker_test": True},
                total_amount=Decimal("0.00"),
                currency="USD",
                expires_at=expires_at,
                guest_confirmation_token_hash=(marker + suffix).ljust(64, "1")[:64],
                guest_confirmation_expires_at=window_start + timedelta(days=1),
            )

        expired_tentative = make_booking(
            BookingStatus.TENTATIVE_HOLD, now - timedelta(minutes=5), "tentative"
        )
        expired_provider = make_booking(
            BookingStatus.PENDING_PROVIDER_CONFIRMATION,
            now - timedelta(minutes=2),
            "provider",
        )
        expired_legacy_payment = make_booking(
            BookingStatus.PENDING_PAYMENT, now - timedelta(minutes=1), "payment"
        )
        future_hold = make_booking(
            BookingStatus.TENTATIVE_HOLD, now + timedelta(minutes=30), "future"
        )
        session.add_all(
            [expired_tentative, expired_provider, expired_legacy_payment, future_hold]
        )
        await session.commit()

        first_count = await expire_booking_holds(session, now=now)
        assert first_count >= 3

        for row in (expired_tentative, expired_provider, expired_legacy_payment, future_hold):
            await session.refresh(row)

        assert expired_tentative.status == BookingStatus.EXPIRED
        assert expired_provider.status == BookingStatus.EXPIRED
        assert expired_legacy_payment.status == BookingStatus.EXPIRED
        assert future_hold.status == BookingStatus.TENTATIVE_HOLD

        second_count = await expire_booking_holds(session, now=now)
        assert second_count == 0
        await session.refresh(future_hold)
        assert future_hold.status == BookingStatus.TENTATIVE_HOLD
