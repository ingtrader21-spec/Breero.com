"""Seed only an isolated APP_ENV=test database for browser certification."""

import asyncio
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from geoalchemy2.elements import WKTElement

from app.config import settings
from app.db.session import SessionLocal
from app.domains.auth.models import User, UserRole
from app.domains.auth.security import hash_password
from app.domains.booking.capacity_models import ProviderAvailabilityRule, ProviderCapacityRule
from app.domains.booking.models import LegalEntity, ServiceArea
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


async def seed() -> None:
    if settings.app_env.lower() != "test":
        raise RuntimeError("Certification fixtures are restricted to APP_ENV=test")
    async with SessionLocal() as session:
        entity = LegalEntity(code="CERT-US", name="Codestra LLC certification", currency="USD")
        session.add(entity)
        await session.flush()
        area = ServiceArea(
            legal_entity_id=entity.id,
            name="Houston certification area",
            country_code="US",
            state_code="TX",
            city="Houston",
            postal_codes=["77001"],
            active=True,
        )
        service = Service(
            slug="certification-plumbing",
            name="Certification plumbing",
            description="Isolated browser certification fixture",
            category="plumbing",
            pricing_model="fixed",
            base_price=Decimal("0.00"),
            duration_minutes=60,
            before_buffer_minutes=15,
            after_buffer_minutes=15,
            quote_required=False,
            is_active=True,
            is_bookable=True,
        )
        admin = User(
            email="certification-admin@breero.com",
            full_name="Certification Admin",
            password_hash=hash_password("Certification-admin-2026"),
            role=UserRole.admin,
            status="ACTIVE",
            email_verified=True,
        )
        provider_user = User(
            email="certification-provider@breero.com",
            full_name="Certification Provider",
            password_hash=hash_password("Certification-provider-2026"),
            role=UserRole.vendor_admin,
            status="ACTIVE",
            email_verified=True,
        )
        session.add_all([area, service, admin, provider_user])
        await session.flush()
        vendor = Vendor(
            legal_name="Certification Provider LLC",
            display_name="Certification Provider",
            email="provider@certification.test",
            phone="+12815550100",
            owner_user_id=provider_user.id,
            status=VendorStatus.ACTIVE,
            onboarding_status="APPROVED",
            compliance_status="APPROVED",
            timezone_id="America/Chicago",
            capabilities=[service.slug],
            home_location=WKTElement("POINT(-95.3698 29.7604)", srid=4326),
        )
        session.add(vendor)
        await session.flush()
        worker = Worker(
            vendor_id=vendor.id,
            user_id=provider_user.id,
            first_name="Certification",
            last_name="Professional",
            email="provider@certification.test",
            phone="+12815550100",
            status=WorkerStatus.ACTIVE,
            available=True,
            default_timezone_id="America/Chicago",
            maximum_jobs_per_day=6,
            maximum_minutes_per_day=600,
        )
        session.add(worker)
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
                ProviderCapacityRule(
                    provider_id=vendor.id,
                    professional_id=worker.id,
                    max_jobs_daily=6,
                    max_minutes_daily=600,
                    max_concurrent_jobs=1,
                    emergency_reserved_jobs=0,
                    emergency_reserved_minutes=0,
                    effective_from=date.today(),
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
        for weekday in range(6):
            session.add(
                ProviderAvailabilityRule(
                    provider_professional_id=worker.id,
                    day_of_week=weekday,
                    start_local_time=time(7),
                    end_local_time=time(19),
                    available=True,
                    emergency_only=False,
                    timezone_id="America/Chicago",
                )
            )
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
