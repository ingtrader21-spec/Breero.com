"""Environment-aware, idempotent BREERO catalog seed.

Launch services are deliberately quote-required and non-bookable unless an operator
explicitly supplies BREERO_BOOKABLE_SERVICE_SLUGS after operational approval.
"""

import asyncio
from decimal import Decimal

from sqlalchemy import select

from app.config import settings
from app.db.session import SessionLocal
from app.domains.booking.models import LegalEntity, ServiceArea
from app.domains.catalog.models import Service

LAUNCH_SERVICES = (
    ("plumbing", "Plumbing", "Plumbing repair and installation requests."),
    ("electrical", "Electrical", "Electrical repair and installation requests."),
    ("handyman", "Handyman", "General home repair and maintenance requests."),
    ("heating", "Heating", "Heating system service requests."),
    ("cooling", "Cooling", "Cooling and air-conditioning service requests."),
    ("appliance-repair", "Appliance repair", "Household appliance repair requests."),
    ("cleaning", "Cleaning", "Residential cleaning service requests."),
    ("locksmith", "Locksmith", "Lock and entry service requests."),
    ("painting", "Painting", "Interior and exterior painting requests."),
    ("carpentry", "Carpentry", "Carpentry and woodwork requests."),
    ("moving-help", "Moving help", "Loading, unloading, and moving-help requests."),
    ("home-maintenance", "Home maintenance", "Recurring and seasonal maintenance requests."),
    ("flooring", "Flooring", "Floor installation, repair, and replacement requests."),
    ("roofing", "Roofing", "Roof inspection, repair, and maintenance requests."),
    ("gutters", "Gutter cleaning & repair", "Gutter cleaning, repair, and maintenance requests."),
    ("windows-doors", "Windows & doors", "Window and door installation and repair requests."),
    ("garage-door", "Garage door service", "Garage door installation and repair requests."),
    ("pest-control", "Pest control", "Residential pest inspection and treatment requests."),
    ("lawn-landscaping", "Lawn & landscaping", "Lawn care and landscaping requests."),
    ("pressure-washing", "Pressure washing", "Exterior surface cleaning requests."),
)

KNOWN_CERTIFICATION_PREFIXES = ("e2e-service-", "test-", "fixture-", "certification-")


async def seed() -> None:
    environment = settings.app_env.lower()
    if environment not in {"staging", "production"}:
        raise RuntimeError("Launch catalog seed requires APP_ENV=staging or production")
    async with SessionLocal() as session:
        entity = await session.scalar(select(LegalEntity).where(LegalEntity.code == "US01"))
        if entity is None:
            entity = LegalEntity(code="US01", name="Codestra LLC", currency="USD", active=True)
            session.add(entity)
            await session.flush()
        else:
            entity.name, entity.currency, entity.active = "Codestra LLC", "USD", True
        area = await session.scalar(select(ServiceArea).where(ServiceArea.name == "Nationwide USA"))
        if area is None:
            area = ServiceArea(legal_entity_id=entity.id, name="Nationwide USA")
            session.add(area)
        area.country_code = "US"
        area.state_code = None
        area.city = None
        area.postal_codes = []
        area.boundary = None
        area.active = True
        rows = list((await session.scalars(select(Service))).all())
        launch_slugs = {row[0] for row in LAUNCH_SERVICES}
        for service in rows:
            certification = service.slug.startswith(KNOWN_CERTIFICATION_PREFIXES)
            legacy_berlin = service.slug == "home-repair-visit"
            if certification or legacy_berlin:
                service.is_active = False
                service.is_bookable = False

        by_slug = {row.slug: row for row in rows}
        for order, (slug, name, description) in enumerate(LAUNCH_SERVICES, start=1):
            launch_service = by_slug.get(slug)
            if launch_service is None:
                launch_service = Service(slug=slug)
                session.add(launch_service)
            launch_service.name = name
            launch_service.description = description
            launch_service.category = "home-services"
            launch_service.base_price = Decimal("200.00")
            launch_service.pricing_model = "evaluation_fee_quote_required"
            launch_service.duration_minutes = 30
            launch_service.is_active = True
            # This release accepts durable requests only. A later protected release may
            # enable booking after provider capacity and payments are certified.
            launch_service.is_bookable = False
            launch_service.sort_order = order

        # Never silently publish an unknown service in launch environments.
        for service in rows:
            if service.slug not in launch_slugs:
                service.is_active = False
                service.is_bookable = False
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
