import secrets
import uuid
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.errors import DomainError
from app.domains.auth.keycloak_provisioner import KeycloakProvisioner
from app.domains.auth.models import Session, User, UserRole
from app.domains.auth.repository import UserRepository
from app.domains.auth.security import (
    REFRESH_TOKEN_TTL_SECONDS,
    create_access_token,
    hash_password,
    hash_token,
    new_opaque_token,
)
from app.domains.booking.capacity_models import BookingCapacityHold, CapacityHoldStatus
from app.domains.booking.hold_service import owner_fingerprint
from app.domains.booking.matching import ProviderMatcher
from app.domains.booking.models import Address, Booking, BookingStatus, Customer
from app.domains.booking.public_schemas import (
    BookingRequestCreate,
    BookingRequestRead,
    PublicAvailabilityRequest,
    PublicAvailabilityResponse,
    PublicSlot,
)
from app.domains.booking.repository import BookingRepository
from app.domains.booking.schemas import AddressValidateRequest
from app.domains.booking.service import AddressService
from app.domains.booking.timezones import local_interval
from app.domains.catalog.repository import CatalogRepository
from app.domains.common.outbox import AuditLog


class PublicAvailabilityService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(self, data: PublicAvailabilityRequest) -> PublicAvailabilityResponse:
        service = await CatalogRepository(self.session).active_detail(data.service_id)
        if not service or not service.is_bookable:
            raise DomainError("SERVICE_NOT_BOOKABLE", "The selected service is not bookable", 422)
        if service.quote_required:
            raise DomainError("QUOTE_REQUIRED", "The selected service requires a quote", 422)
        if data.requested_date.weekday() == 6 and not (
            data.emergency and service.emergency_eligible and service.sunday_emergency_eligible
        ):
            raise DomainError("SUNDAY_EMERGENCY_ONLY", "Sunday is limited to eligible emergency service", 422)
        validated = await AddressService(self.session).validate(
            AddressValidateRequest(address=data.address.single_line())
        )
        if not validated.serviceable or not validated.address_id:
            raise DomainError("OUTSIDE_SERVICE_AREA", "The address is outside an active service area", 422)
        address = await self.session.get(Address, validated.address_id)
        if not address:
            raise DomainError("INVALID_ADDRESS", "Validated address was not persisted", 500)
        duration = service.duration_minutes or 60
        consumed = duration + service.before_buffer_minutes + service.after_buffer_minutes
        cursor = datetime.combine(data.requested_date, time(7))
        boundary = datetime.combine(data.requested_date, time(19))
        slots: list[PublicSlot] = []
        matcher = ProviderMatcher(self.session)
        while cursor + timedelta(minutes=consumed) <= boundary:
            end = cursor + timedelta(minutes=consumed)
            interval = local_interval(cursor, end, address.timezone_name)
            if await matcher.candidates(
                service,
                address,
                interval.start_utc,
                interval.end_utc,
                emergency=data.emergency,
            ):
                slots.append(
                    PublicSlot(
                        start_local=cursor.strftime("%H:%M"),
                        end_local=(cursor + timedelta(minutes=duration)).strftime("%H:%M"),
                    )
                )
            cursor += timedelta(minutes=30)
        return PublicAvailabilityResponse(
            timezone=address.timezone_name,
            date=data.requested_date,
            address_id=address.id,
            slots=slots,
            reason=None if slots else "NO_CAPACITY",
        )


class BookingRequestService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def create(
        self, data: BookingRequestCreate, authenticated_user: User | None
    ) -> BookingRequestRead:
        hold = await self.session.scalar(
            select(BookingCapacityHold)
            .where(BookingCapacityHold.id == data.hold_id)
            .with_for_update()
        )
        now = datetime.now(UTC)
        if (
            hold
            and hold.owner_fingerprint_hash == owner_fingerprint(data.booking_session)
            and hold.status == CapacityHoldStatus.CONVERTED
            and hold.booking_id
        ):
            existing = await self.session.get(Booking, hold.booking_id)
            if existing:
                return BookingRequestRead(
                    public_reference=existing.reference,
                    status=existing.status.value,
                    timezone=existing.service_timezone_id,
                    start_at_utc=existing.window_start,
                    end_at_utc=existing.window_end,
                    account_created=False,
                )
        if (
            not hold
            or hold.owner_fingerprint_hash != owner_fingerprint(data.booking_session)
            or hold.status != CapacityHoldStatus.HELD
            or hold.expires_at <= now
        ):
            raise DomainError("HOLD_EXPIRED", "The selected capacity hold is invalid or expired", 409)
        email = str(data.customer.email).strip().lower()
        user = await self.users.by_email(email)
        account_created = False
        access_token = refresh_token = None
        if user:
            if not authenticated_user or authenticated_user.id != user.id:
                raise DomainError(
                    "AUTH_REQUIRED",
                    "Sign in to link this request to the existing account",
                    401,
                )
        else:
            account_created = True
            keycloak_subject = None
            if settings.keycloak_enabled and settings.keycloak_provisioning_enabled:
                keycloak_subject = await KeycloakProvisioner().ensure_client(
                    email, data.customer.first_name, data.customer.last_name
                )
            user = await self.users.add(
                User(
                    email=email,
                    phone=data.customer.phone,
                    full_name=f"{data.customer.first_name} {data.customer.last_name}".strip(),
                    password_hash=hash_password(secrets.token_urlsafe(48)),
                    role=UserRole.customer,
                    status="ACTIVE",
                    password_set_required=True,
                    keycloak_subject=keycloak_subject,
                    keycloak_issuer=settings.keycloak_issuer.rstrip("/") if keycloak_subject else None,
                    keycloak_username=email if keycloak_subject else None,
                    keycloak_linked_at=now if keycloak_subject else None,
                )
            )
            if not settings.keycloak_enabled:
                refresh_token = new_opaque_token()
                self.session.add(
                    Session(
                        user_id=user.id,
                        token_hash=hash_token(refresh_token),
                        family_id=uuid.uuid4(),
                        expires_at=now + timedelta(seconds=REFRESH_TOKEN_TTL_SECONDS),
                    )
                )
                access_token = create_access_token(
                    user.id, user.role.value, credential_version=user.credential_version
                )
        customer = await self.session.scalar(
            select(Customer).where(Customer.user_id == user.id).with_for_update()
        )
        if not customer:
            customer = Customer(
                user_id=user.id,
                first_name=data.customer.first_name,
                last_name=data.customer.last_name,
                email=email,
                phone=data.customer.phone,
            )
            self.session.add(customer)
            await self.session.flush()
        address = await self.session.get(Address, hold.address_id)
        if not address or not address.service_area_id:
            raise DomainError("OUTSIDE_SERVICE_AREA", "Service address is no longer eligible", 422)
        address.customer_id = customer.id
        legal_entity = await BookingRepository(self.session).legal_entity_for_area(
            address.service_area_id
        )
        if not legal_entity:
            raise DomainError("OUTSIDE_SERVICE_AREA", "Service area has no active legal entity", 422)
        booking = Booking(
            reference=f"BR-{secrets.token_urlsafe(12)}",
            idempotency_key=f"hold:{hold.id}",
            idempotency_request_hash=hash_token(str(hold.id)),
            customer_id=customer.id,
            address_id=address.id,
            legal_entity_id=legal_entity.id,
            service_id=hold.service_id,
            provider_worker_id=None,
            service_timezone_id=hold.timezone_id,
            window_start=hold.slot_start_utc,
            window_end=hold.slot_end_utc,
            status=BookingStatus.PENDING_MANUAL_DISPATCH,
            pricing_snapshot={"quote_required": False, "payments_enabled": False},
            total_amount=Decimal("0.00"),
            currency=legal_entity.currency,
            expires_at=now + timedelta(days=30),
            guest_confirmation_token_hash=hash_token(new_opaque_token()),
            guest_confirmation_expires_at=now + timedelta(days=30),
            request_note=data.notes,
        )
        self.session.add(booking)
        await self.session.flush()
        hold.booking_id = booking.id
        hold.status = CapacityHoldStatus.CONVERTED
        hold.converted_at = now
        self.session.add(
            AuditLog(
                actor_id=user.id,
                actor_type="customer",
                action="booking.requested",
                resource_type="booking",
                resource_id=booking.id,
                metadata_json={
                    "status": BookingStatus.PENDING_MANUAL_DISPATCH.value,
                    "timezone_id": hold.timezone_id,
                    "account_created": account_created,
                },
                created_at=now,
            )
        )
        await self.session.commit()
        return BookingRequestRead(
            public_reference=booking.reference,
            status=booking.status.value,
            timezone=booking.service_timezone_id,
            start_at_utc=booking.window_start,
            end_at_utc=booking.window_end,
            account_created=account_created,
            access_token=access_token,
            refresh_token=refresh_token,
            password_set_required=account_created,
        )

    async def public_status(self, reference: str) -> dict:
        booking = await self.session.scalar(select(Booking).where(Booking.reference == reference))
        if not booking:
            raise DomainError("BOOKING_NOT_FOUND", "Request not found", 404)
        public_statuses = {
            BookingStatus.REQUESTED,
            BookingStatus.PENDING_REVIEW,
            BookingStatus.PENDING_MANUAL_DISPATCH,
            BookingStatus.PROVIDER_ASSIGNED,
            BookingStatus.CONFIRMED,
            BookingStatus.CANCELLED,
            BookingStatus.RESCHEDULED,
        }
        status = booking.status if booking.status in public_statuses else BookingStatus.PENDING_REVIEW
        return {"public_reference": booking.reference, "status": status.value}
