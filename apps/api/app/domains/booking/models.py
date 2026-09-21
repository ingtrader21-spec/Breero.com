import enum
import uuid
from datetime import date, datetime, time
from decimal import Decimal

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domains.common.models import TimestampMixin, UUIDPrimaryKeyMixin


class BookingStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    REQUESTED = "REQUESTED"
    PENDING_REVIEW = "PENDING_REVIEW"
    ADDRESS_VALIDATED = "ADDRESS_VALIDATED"
    COVERAGE_CONFIRMED = "COVERAGE_CONFIRMED"
    AVAILABILITY_FOUND = "AVAILABILITY_FOUND"
    CAPACITY_HELD = "CAPACITY_HELD"
    AWAITING_ASSIGNMENT = "AWAITING_ASSIGNMENT"
    PROVIDER_ASSIGNED = "PROVIDER_ASSIGNED"
    PENDING_MANUAL_DISPATCH = "PENDING_MANUAL_DISPATCH"
    TENTATIVE_HOLD = "TENTATIVE_HOLD"
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PENDING_PROVIDER_CONFIRMATION = "PENDING_PROVIDER_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    EN_ROUTE = "EN_ROUTE"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    NO_COVERAGE = "NO_COVERAGE"
    NO_CAPACITY = "NO_CAPACITY"
    QUOTE_REQUIRED = "QUOTE_REQUIRED"
    PROVIDER_DECLINED = "PROVIDER_DECLINED"
    REASSIGNMENT_REQUIRED = "REASSIGNMENT_REQUIRED"
    RESCHEDULED = "RESCHEDULED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


CAPACITY_HOLDING_STATUSES = frozenset(
    {BookingStatus.TENTATIVE_HOLD, BookingStatus.PENDING_PROVIDER_CONFIRMATION}
)
EXPIRING_BOOKING_STATUSES = CAPACITY_HOLDING_STATUSES | {BookingStatus.PENDING_PAYMENT}


class LegalEntity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "legal_entities"
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ServiceArea(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "service_areas"
    legal_entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("legal_entities.id"))
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(2), index=True)
    state_code: Mapped[str | None] = mapped_column(String(3), index=True)
    city: Mapped[str | None] = mapped_column(String(120), index=True)
    postal_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    center: Mapped[object | None] = mapped_column(Geometry("POINT", srid=4326))
    radius_meters: Mapped[int | None] = mapped_column(Integer)
    boundary: Mapped[object | None] = mapped_column(Geometry("MULTIPOLYGON", srid=4326))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    emergency_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class Address(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "addresses"
    formatted_address: Mapped[str] = mapped_column(String(500), nullable=False)
    label: Mapped[str] = mapped_column(String(40), nullable=False, default="Home")
    line1: Mapped[str] = mapped_column(String(200), nullable=False)
    line2: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    county: Mapped[str | None] = mapped_column(String(120))
    state_code: Mapped[str | None] = mapped_column(String(3))
    postal_code: Mapped[str] = mapped_column(String(32), nullable=False)
    postal_code_plus4: Mapped[str | None] = mapped_column(String(4))
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    location: Mapped[object] = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    service_area_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("service_areas.id"))
    geocoding_provider: Mapped[str] = mapped_column(String(40), default="provided")
    timezone_name: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    timezone_source: Mapped[str] = mapped_column(String(40), nullable=False, default="geocoding")
    address_validation_status: Mapped[str] = mapped_column(String(32), nullable=False, default="VALIDATED")
    validation_status: Mapped[str] = mapped_column(String(32), nullable=False, default="VALID")
    provider_reference: Mapped[str | None] = mapped_column(String(255))
    validation_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    service_zone_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("service_zones.id"), index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class AvailabilityRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "availability_rules"
    service_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    service_area_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_areas.id"))
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    slot_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    active_from: Mapped[date | None] = mapped_column(Date)
    active_to: Mapped[date | None] = mapped_column(Date)


class ProviderServiceCoverage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Operator-approved ZIP/service coverage; absence always means unavailable."""

    __tablename__ = "provider_service_coverage"
    __table_args__ = (UniqueConstraint("worker_id", "service_id", "postal_code"),)
    worker_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workers.id", ondelete="CASCADE"), index=True)
    service_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    postal_code: Mapped[str] = mapped_column(String(10), index=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ProviderWorkingHours(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "provider_working_hours"
    __table_args__ = (UniqueConstraint("worker_id", "weekday"),)
    worker_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workers.id", ondelete="CASCADE"), index=True)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class Customer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customers"
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(40), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True
    )
    preferred_language: Mapped[str] = mapped_column(String(12), nullable=False, default="en-US")
    default_address_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class Booking(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bookings"
    reference: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    idempotency_request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True)
    address_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("addresses.id"))
    legal_entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("legal_entities.id"))
    service_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    provider_worker_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workers.id"), index=True)
    service_timezone_id: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    recommended_provider_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("vendors.id"), index=True)
    recommended_professional_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workers.id"), index=True)
    assignment_score: Mapped[int | None] = mapped_column(Integer)
    assignment_reason: Mapped[str | None] = mapped_column(String(500))
    request_note: Mapped[str | None] = mapped_column(Text)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, name="booking_status"), default=BookingStatus.REQUESTED
    )
    pricing_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    guest_confirmation_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    guest_confirmation_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    guest_confirmation_revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )


class BookingAnswer(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "booking_answers"
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"))
    question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    value: Mapped[str] = mapped_column(Text, nullable=False)
