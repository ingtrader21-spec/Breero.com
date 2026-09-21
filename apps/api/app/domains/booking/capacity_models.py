import enum
import uuid
from datetime import date, datetime, time

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domains.common.models import TimestampMixin, UUIDPrimaryKeyMixin


class CapacityHoldStatus(str, enum.Enum):
    HELD = "HELD"
    CONVERTED = "CONVERTED"
    EXPIRED = "EXPIRED"
    RELEASED = "RELEASED"


class AvailabilityExceptionReason(str, enum.Enum):
    VACATION = "VACATION"
    SICK = "SICK"
    PERSONAL = "PERSONAL"
    TRAINING = "TRAINING"
    VEHICLE = "VEHICLE"
    HOLIDAY = "HOLIDAY"
    MANUAL_BLOCK = "MANUAL_BLOCK"
    OTHER = "OTHER"


class AssignmentMethod(str, enum.Enum):
    MANUAL = "MANUAL"
    SUGGESTED = "SUGGESTED"
    AUTOMATIC = "AUTOMATIC"


class ServiceZone(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "service_zones"
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    state: Mapped[str | None] = mapped_column(String(3), index=True)
    county: Mapped[str | None] = mapped_column(String(120), index=True)
    city: Mapped[str | None] = mapped_column(String(120), index=True)
    postal_code: Mapped[str | None] = mapped_column(String(5), index=True)
    postal_prefix: Mapped[str | None] = mapped_column(String(5), index=True)
    timezone_id: Mapped[str | None] = mapped_column(String(64))
    center: Mapped[object | None] = mapped_column(Geometry("POINT", srid=4326))
    radius_meters: Mapped[int | None] = mapped_column(Integer)
    boundary: Mapped[object | None] = mapped_column(Geometry("MULTIPOLYGON", srid=4326))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    regular_service_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    emergency_service_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ServiceZonePostalCode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "service_zone_postal_codes"
    __table_args__ = (UniqueConstraint("service_zone_id", "postal_code"),)
    service_zone_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("service_zones.id", ondelete="CASCADE"), index=True
    )
    postal_code: Mapped[str] = mapped_column(String(5), index=True)
    city: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str] = mapped_column(String(3), index=True)
    county: Mapped[str | None] = mapped_column(String(120))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)


class ProviderAvailabilityRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "provider_availability_rules"
    __table_args__ = (
        UniqueConstraint(
            "provider_professional_id", "day_of_week", "start_local_time", "end_local_time"
        ),
    )
    provider_professional_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workers.id", ondelete="CASCADE"), index=True
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    start_local_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_local_time: Mapped[time] = mapped_column(Time, nullable=False)
    available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    emergency_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    timezone_id: Mapped[str] = mapped_column(String(64), nullable=False)


class ProviderAvailabilityException(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "provider_availability_exceptions"
    provider_professional_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workers.id", ondelete="CASCADE"), index=True
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    timezone_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[AvailabilityExceptionReason] = mapped_column(
        Enum(AvailabilityExceptionReason, name="availability_exception_reason")
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ACTIVE")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class ProviderCapacityRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "provider_capacity_rules"
    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vendors.id", ondelete="CASCADE"), index=True
    )
    professional_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workers.id", ondelete="CASCADE"), index=True
    )
    max_jobs_daily: Mapped[int] = mapped_column(Integer, nullable=False)
    max_minutes_daily: Mapped[int] = mapped_column(Integer, nullable=False)
    max_concurrent_jobs: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    emergency_reserved_jobs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    emergency_reserved_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_until: Mapped[date | None] = mapped_column(Date)


class BookingCapacityHold(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "booking_capacity_holds"
    booking_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), index=True
    )
    service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("services.id"), index=True)
    address_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("addresses.id"), index=True)
    provider_candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vendors.id"), index=True)
    professional_candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workers.id"), index=True
    )
    slot_start_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    slot_end_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    timezone_id: Mapped[str] = mapped_column(String(64), nullable=False)
    capacity_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[CapacityHoldStatus] = mapped_column(
        Enum(CapacityHoldStatus, name="capacity_hold_status"), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    owner_fingerprint_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)


class ProviderAssignmentHistory(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "provider_assignment_history"
    booking_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), index=True
    )
    previous_provider_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("vendors.id"))
    new_provider_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("vendors.id"))
    previous_professional_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workers.id"))
    new_professional_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workers.id"))
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    assignment_method: Mapped[AssignmentMethod] = mapped_column(
        Enum(AssignmentMethod, name="assignment_method")
    )
    score_at_assignment: Mapped[int | None] = mapped_column(Integer)
    performed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
