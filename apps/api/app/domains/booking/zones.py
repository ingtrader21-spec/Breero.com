from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.booking.capacity_models import ServiceZone, ServiceZonePostalCode
from app.domains.booking.postal import normalize_state, normalize_us_postal_code


@dataclass(frozen=True)
class ServiceZoneMatch:
    zone: ServiceZone
    postal: ServiceZonePostalCode


class ServiceZoneResolver:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def resolve_postal(self, postal_code: str, state: str, city: str | None = None) -> ServiceZoneMatch | None:
        postal = normalize_us_postal_code(postal_code)
        state_code = normalize_state(state)
        statement = (
            select(ServiceZonePostalCode, ServiceZone)
            .join(ServiceZone, ServiceZone.id == ServiceZonePostalCode.service_zone_id)
            .where(
                ServiceZonePostalCode.postal_code == postal.postal_code,
                ServiceZonePostalCode.state == state_code,
                ServiceZonePostalCode.active.is_(True),
                ServiceZone.active.is_(True),
            )
            .order_by(ServiceZonePostalCode.priority, ServiceZonePostalCode.id)
        )
        rows = list((await self.session.execute(statement)).all())
        if city:
            normalized_city = city.strip().casefold()
            city_rows = [row for row in rows if not row[0].city or row[0].city.casefold() == normalized_city]
            if city_rows:
                rows = city_rows
        if not rows:
            return None
        zone_postal, zone = rows[0]
        return ServiceZoneMatch(zone=zone, postal=zone_postal)
