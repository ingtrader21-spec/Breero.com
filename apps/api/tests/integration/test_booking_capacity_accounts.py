import asyncio
import uuid
from datetime import UTC, date, datetime, time, timedelta

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import select

from app.core.errors import DomainError
from app.db.session import SessionLocal
from app.domains.auth.models import UserRole
from app.domains.auth.schemas import ProviderRegisterRequest
from app.domains.auth.service import AuthService
from app.domains.booking.capacity_models import ProviderAvailabilityRule
from app.domains.booking.hold_service import CapacityHoldService
from app.domains.booking.models import Address, LegalEntity, ServiceArea
from app.domains.catalog.models import Service
from app.domains.workforce.models import (
    ProviderCredential,
    ProviderCredentialType,
    Vendor,
    VendorStatus,
    Worker,
    WorkerStatus,
)
from app.domains.workforce.provider_models import ProviderService, ProviderServiceArea


@pytest.mark.asyncio
async def test_provider_registration_creates_pending_ineligible_account() -> None:
    marker = uuid.uuid4().hex
    async with SessionLocal() as session:
        service = Service(
            slug=f"provider-registration-{marker}",
            name="Provider registration test",
            category="test",
            pricing_model="quote_required",
            duration_minutes=60,
            is_active=True,
            is_bookable=False,
        )
        session.add(service)
        await session.commit()
        response, vendor = await AuthService(session).register_provider(
            ProviderRegisterRequest(
                email=f"provider-{marker}@example.com",
                password="safe-provider-password",
                contact_name="Provider Owner",
                phone="+12815550123",
                legal_name="Provider Test LLC",
                display_name="Provider Test",
                business_address="100 Test Street",
                city="Houston",
                state="TX",
                postal_code="77001",
                timezone_id="America/Chicago",
                service_slugs=[service.slug],
                service_postal_codes=["77001"],
            )
        )
        assert response.user.role == UserRole.vendor_admin
        assert vendor.status == VendorStatus.PENDING
        assert vendor.onboarding_status == "PENDING"
        worker = await session.scalar(select(Worker).where(Worker.vendor_id == vendor.id))
        mapping = await session.scalar(
            select(ProviderService).where(ProviderService.provider_id == vendor.id)
        )
        area = await session.scalar(
            select(ProviderServiceArea).where(ProviderServiceArea.provider_id == vendor.id)
        )
        assert worker and worker.status == WorkerStatus.INVITED and worker.available is False
        assert mapping and mapping.active is False and mapping.approval_status == "PENDING"
        assert area and area.active is False and area.approval_status == "PENDING"


@pytest.mark.asyncio
async def test_simultaneous_holds_cannot_double_book_one_professional() -> None:
    marker = uuid.uuid4().hex
    start_local = datetime.now().replace(second=0, microsecond=0) + timedelta(days=2)
    while start_local.weekday() == 6:
        start_local += timedelta(days=1)
    start_local = start_local.replace(hour=9, minute=0)
    async with SessionLocal() as session:
        entity = LegalEntity(code=f"TEST-{marker[:8]}", name="Test entity", currency="USD")
        session.add(entity)
        await session.flush()
        area = ServiceArea(
            legal_entity_id=entity.id,
            name=f"Test area {marker}",
            country_code="US",
            state_code="TX",
            city="Houston",
            postal_codes=["77001"],
            active=True,
        )
        service = Service(
            slug=f"capacity-{marker}",
            name="Capacity test",
            category="test",
            pricing_model="fixed",
            base_price=100,
            duration_minutes=60,
            quote_required=False,
            is_active=True,
            is_bookable=True,
        )
        vendor = Vendor(
            legal_name="Capacity Test LLC",
            display_name="Capacity Test",
            email=f"capacity-{marker}@example.test",
            phone="+12815550124",
            status=VendorStatus.ACTIVE,
            onboarding_status="APPROVED",
            compliance_status="APPROVED",
            capabilities=[service.slug],
        )
        session.add_all([area, service, vendor])
        await session.flush()
        worker = Worker(
            vendor_id=vendor.id,
            first_name="Capacity",
            last_name="Worker",
            email=f"worker-{marker}@example.test",
            phone="+12815550125",
            status=WorkerStatus.ACTIVE,
            available=True,
            maximum_jobs_per_day=1,
            maximum_minutes_per_day=60,
            default_timezone_id="America/Chicago",
        )
        address = Address(
            formatted_address="100 Main St, Houston, TX 77001",
            line1="100 Main St",
            city="Houston",
            state_code="TX",
            postal_code="77001",
            country_code="US",
            location=WKTElement("POINT(-95.3698 29.7604)", srid=4326),
            service_area_id=area.id,
            geocoding_provider="test",
            timezone_name="America/Chicago",
        )
        session.add_all([worker, address])
        await session.flush()
        session.add_all(
            [
                ProviderService(
                    provider_id=vendor.id,
                    service_id=service.id,
                    active=True,
                    approval_status="APPROVED",
                ),
                ProviderServiceArea(
                    provider_id=vendor.id,
                    professional_id=worker.id,
                    area_type="ZIP",
                    postal_code="77001",
                    state="TX",
                    active=True,
                    approval_status="APPROVED",
                ),
                ProviderAvailabilityRule(
                    provider_professional_id=worker.id,
                    day_of_week=start_local.weekday(),
                    start_local_time=time(7),
                    end_local_time=time(19),
                    available=True,
                    emergency_only=False,
                    timezone_id="America/Chicago",
                ),
                ProviderCredential(
                    vendor_id=vendor.id,
                    credential_type=ProviderCredentialType.LICENSE,
                    jurisdiction="TX",
                    verified=True,
                    verified_at=datetime.now(UTC),
                    expires_on=date.today() + timedelta(days=365),
                ),
                ProviderCredential(
                    vendor_id=vendor.id,
                    credential_type=ProviderCredentialType.INSURANCE,
                    jurisdiction="US",
                    verified=True,
                    verified_at=datetime.now(UTC),
                    expires_on=date.today() + timedelta(days=365),
                ),
            ]
        )
        await session.commit()
        service_id, address_id = service.id, address.id

    async def reserve(suffix: str):
        async with SessionLocal() as session:
            return await CapacityHoldService(session).create(
                service_id,
                address_id,
                start_local,
                "America/Chicago",
                f"booking-session-{suffix}-{marker}",
                f"idempotency-hold-{suffix}-{marker}",
            )

    outcomes = await asyncio.gather(reserve("a"), reserve("b"), return_exceptions=True)
    successes = [outcome for outcome in outcomes if not isinstance(outcome, Exception)]
    failures = [outcome for outcome in outcomes if isinstance(outcome, DomainError)]
    assert len(successes) == 1
    assert len(failures) == 1
    assert failures[0].code in {"NO_CAPACITY", "HOLD_CONFLICT"}
