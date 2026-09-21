import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from geoalchemy2.elements import WKTElement
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.domains.booking.models import Address, Booking, BookingAnswer, BookingStatus, Customer
from app.domains.booking.repository import BookingRepository
from app.domains.booking.schemas import (
    AddressValidateRequest,
    AddressValidationResponse,
    AvailabilitySearchRequest,
    AvailabilitySlot,
    BookingCreateRequest,
)
from app.domains.catalog.repository import CatalogRepository
from app.domains.common.us import US_STATES_AND_DC
from app.integrations.geocoding import GeocodingAdapter


def evaluation_fee(local_start: datetime) -> Decimal:
    return Decimal("300.00") if local_start.weekday() == 6 else Decimal("200.00")


class AddressService:
    def __init__(self, session: AsyncSession, geocoder: GeocodingAdapter | None = None) -> None:
        self.session = session
        self.repository = BookingRepository(session)
        self.geocoder = geocoder or GeocodingAdapter()

    async def validate(self, payload: AddressValidateRequest) -> AddressValidationResponse:
        # Customer-supplied coordinates never establish coverage; Geoapify is authoritative.
        resolved = await self.geocoder.geocode(payload.address)
        if (
            resolved.country_code != "US"
            or resolved.state_code not in US_STATES_AND_DC
            or not resolved.postal_code
            or not resolved.timezone_name
        ):
            return AddressValidationResponse(
                serviceable=False, formatted_address=resolved.formatted_address,
                address_id=None, service_area_id=None, legal_entity_code=None,
            )
        match = await self.repository.service_area_at(
            resolved.longitude, resolved.latitude, resolved.country_code,
            resolved.state_code, resolved.city, resolved.postal_code,
        )
        if not match:
            return AddressValidationResponse(
                serviceable=False,
                formatted_address=resolved.formatted_address,
                address_id=None,
                service_area_id=None,
                legal_entity_code=None,
            )
        area, entity = match
        address = Address(
            formatted_address=resolved.formatted_address,
            line1=resolved.line1,
            city=resolved.city,
            state_code=resolved.state_code,
            postal_code=resolved.postal_code,
            postal_code_plus4=resolved.postal_code_plus4,
            country_code=resolved.country_code,
            service_area_id=area.id,
            geocoding_provider=resolved.provider,
            timezone_name=resolved.timezone_name,
            timezone_source=resolved.provider,
            address_validation_status="VALIDATED",
            location=WKTElement(f"POINT({resolved.longitude} {resolved.latitude})", srid=4326),
        )
        await self.repository.add_address(address)
        await self.session.commit()
        return AddressValidationResponse(
            serviceable=True,
            formatted_address=address.formatted_address,
            address_id=address.id,
            service_area_id=area.id,
            legal_entity_code=entity.code,
        )


class AvailabilityService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = BookingRepository(session)

    async def search(self, payload: AvailabilitySearchRequest) -> list[AvailabilitySlot]:
        address = await self.repository.address(payload.address_id)
        if not address or not address.service_area_id:
            raise DomainError(
                "ADDRESS_NOT_SERVICEABLE", "Address is outside an active service area", 422
            )
        # Opt-in, same as the ProviderService check in eligible_provider_hours: a
        # zone with no explicit per-service offering configured behaves exactly as
        # before (covered by the zone generally). Once an offering row exists for
        # this zone+service, it becomes authoritative for regular-service bookings.
        offering = await self.repository.zone_offering(address.service_area_id, payload.service_id)
        if offering is not None and not (offering.active and offering.regular_service_enabled):
            raise DomainError(
                "SERVICE_NOT_OFFERED_IN_ZONE",
                "This service is not offered at the selected address.",
                422,
            )
        slots: list[AvailabilitySlot] = []
        try:
            local_zone = ZoneInfo(address.timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise DomainError("ADDRESS_TIMEZONE_INVALID", "Service address timezone is invalid", 422) from exc
        current = payload.date_from
        while current <= payload.date_to:
            capacity_by_slot: dict[tuple[datetime, datetime], int] = {}
            provider_hours = await self.repository.eligible_provider_hours(
                payload.service_id, address.postal_code, current.weekday()
            )
            for worker, hours in provider_hours:
                cursor = datetime.combine(current, hours.start_time, tzinfo=local_zone)
                boundary = datetime.combine(current, hours.end_time, tzinfo=local_zone)
                while cursor + timedelta(minutes=60) <= boundary:
                    start, end = cursor.astimezone(UTC), (cursor + timedelta(minutes=60)).astimezone(UTC)
                    used = await self.repository.provider_booking_count(worker.id, start, end)
                    if used < hours.capacity:
                        capacity_by_slot[(start, end)] = capacity_by_slot.get((start, end), 0) + 1
                    cursor += timedelta(minutes=60)
            for (start, end), capacity in sorted(capacity_by_slot.items()):
                held = await self.repository.booking_count(payload.service_id, start, end)
                if remaining := max(capacity - held, 0):
                    slots.append(
                        AvailabilitySlot(start=start, end=end, remaining_capacity=remaining)
                    )
            current += timedelta(days=1)
        return slots


class BookingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = BookingRepository(session)
        self.availability = AvailabilityService(session)

    async def create(self, payload: BookingCreateRequest, idempotency_key: str) -> Booking:
        request_hash = hashlib.sha256(
            json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        await self.repository.lock_idempotency_key(idempotency_key)
        existing = await self.repository.booking_by_idempotency_key(idempotency_key)
        if existing:
            if existing.idempotency_request_hash not in {"legacy", request_hash}:
                raise DomainError(
                    "IDEMPOTENCY_CONFLICT",
                    "The idempotency key was already used for a different booking request",
                    409,
                )
            return existing
        if payload.window.start >= payload.window.end or payload.window.start <= datetime.now(UTC):
            raise DomainError("INVALID_BOOKING_WINDOW", "Booking window must be in the future", 422)
        service = await CatalogRepository(self.session).active_detail(str(payload.service_id))
        if service and not service.is_bookable:
            raise DomainError(
                "SERVICE_NOT_BOOKABLE",
                "This service currently supports requests only and cannot be booked",
                409,
            )
        address = await self.repository.address(payload.address_id)
        if not address or not address.service_area_id:
            raise DomainError(
                "ADDRESS_NOT_SERVICEABLE", "Address is outside an active service area", 422
            )
        try:
            local_zone = ZoneInfo(address.timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise DomainError("ADDRESS_TIMEZONE_INVALID", "Service address timezone is invalid", 422) from exc
        local_date = payload.window.start.astimezone(local_zone).date()
        await self.repository.lock_slot(payload.service_id, payload.window.start, payload.window.end)
        slots = await self.availability.search(
            AvailabilitySearchRequest(
                service_id=payload.service_id,
                address_id=payload.address_id,
                date_from=local_date,
                date_to=local_date,
            )
        )
        if not any(
            slot.start == payload.window.start and slot.end == payload.window.end for slot in slots
        ):
            raise DomainError(
                "SLOT_UNAVAILABLE", "The selected time slot is no longer available", 409
            )
        local_weekday = payload.window.start.astimezone(local_zone).weekday()
        eligible = await self.repository.eligible_provider_hours(
            payload.service_id, address.postal_code, local_weekday
        )
        if not eligible:
            raise DomainError("SLOT_UNAVAILABLE", "Provider capacity is no longer available", 409)
        entity = await self.repository.legal_entity_for_area(address.service_area_id)
        if not entity:
            raise DomainError("LEGAL_ENTITY_NOT_FOUND", "No legal entity serves this address", 422)
        if not service:
            raise DomainError("SERVICE_NOT_FOUND", "Service is not available", 404)
        supplied = {answer.question_id for answer in payload.answers}
        required = {
            question.id
            for question in service.questions
            if question.is_active and question.required
        }
        if missing := required - supplied:
            raise DomainError(
                "REQUIRED_ANSWERS_MISSING", f"Missing {len(missing)} required answer(s)", 422
            )
        valid_questions = {question.id for question in service.questions if question.is_active}
        if supplied - valid_questions:
            raise DomainError(
                "INVALID_QUESTION", "An answer references an invalid service question", 422
            )
        # This release records a quote-required request and never computes or collects an online fee.
        customer = await self.repository.customer_for_email(str(payload.customer.email).lower())
        if customer is None:
            customer = Customer(
                first_name=payload.customer.first_name,
                last_name=payload.customer.last_name,
                email=str(payload.customer.email).lower(),
                phone=payload.customer.phone,
            )
            await self.repository.add(customer)
        if customer.user_id and address.customer_id is None:
            address.customer_id = customer.id
        booking = Booking(
            reference=f"BR-{secrets.token_hex(5).upper()}",
            idempotency_key=idempotency_key,
            idempotency_request_hash=request_hash,
            customer_id=customer.id,
            address_id=address.id,
            legal_entity_id=entity.id,
            service_id=payload.service_id,
            provider_worker_id=None,
            window_start=payload.window.start,
            window_end=payload.window.end,
            status=BookingStatus.TENTATIVE_HOLD,
            pricing_snapshot={
                "service_id": str(payload.service_id),
                "service_name": service.name,
                "evaluation_fee": "NOT_COLLECTED_ONLINE",
                "job_price": "QUOTE_REQUIRED",
                "evaluation_minutes": 30,
                "appointment_interval_minutes": 60,
                "total": "QUOTE_REQUIRED",
                "currency": entity.currency,
            },
            total_amount=Decimal("0.00"),
            currency=entity.currency,
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
            guest_confirmation_token_hash="pending",
            guest_confirmation_expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
        guest_token = secrets.token_urlsafe(32)
        booking.guest_confirmation_token_hash = hashlib.sha256(guest_token.encode()).hexdigest()
        await self.repository.add(booking)
        # The reusable token is returned only at this creation boundary; only its hash is stored.
        setattr(booking, "guest_confirmation_token", guest_token)
        for answer in payload.answers:
            await self.repository.add(
                BookingAnswer(
                    booking_id=booking.id, question_id=answer.question_id, value=answer.value
                )
            )
        await self.session.commit()
        return booking
