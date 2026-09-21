import enum
import uuid
from datetime import date, datetime

from geoalchemy2 import Geography
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class VendorStatus(str, enum.Enum):
    PENDING = "PENDING"
    UNDER_REVIEW = "UNDER_REVIEW"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    SUSPENDED = "SUSPENDED"
    REJECTED = "REJECTED"
    OFFBOARDED = "OFFBOARDED"


class WorkerStatus(str, enum.Enum):
    INVITED = "INVITED"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class ProviderCredentialType(str, enum.Enum):
    LICENSE = "LICENSE"
    INSURANCE = "INSURANCE"


class ProviderApplicationStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    INFORMATION_REQUESTED = "INFORMATION_REQUESTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    legal_name: Mapped[str] = mapped_column(String(180))
    display_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(320), unique=True)
    phone: Mapped[str] = mapped_column(String(32))
    provider_type: Mapped[str] = mapped_column(String(32), nullable=False, default="COMPANY")
    business_address: Mapped[str | None] = mapped_column(String(240))
    city: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(3))
    postal_code: Mapped[str | None] = mapped_column(String(10))
    onboarding_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    compliance_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    timezone_id: Mapped[str | None] = mapped_column(String(64))
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), unique=True)
    status: Mapped[VendorStatus] = mapped_column(
        Enum(VendorStatus, name="vendor_status"), index=True
    )
    service_radius_meters: Mapped[int] = mapped_column(Integer, default=40000)
    home_location: Mapped[object | None] = mapped_column(Geography("POINT", srid=4326))
    capabilities: Mapped[list] = mapped_column(JSONB, default=list)
    payout_profile_ref: Mapped[str | None] = mapped_column(String(255))
    odoo_partner_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Worker(Base):
    __tablename__ = "workers"
    __table_args__ = (UniqueConstraint("vendor_id", "email"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vendors.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), unique=True)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(320))
    phone: Mapped[str] = mapped_column(String(32))
    status: Mapped[WorkerStatus] = mapped_column(
        Enum(WorkerStatus, name="worker_status"), index=True
    )
    skills: Mapped[list] = mapped_column(JSONB, default=list)
    current_location: Mapped[object | None] = mapped_column(Geography("POINT", srid=4326))
    location_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    default_timezone_id: Mapped[str | None] = mapped_column(String(64))
    maximum_jobs_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    maximum_minutes_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=600)
    sunday_emergency_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkerLocationEvent(Base):
    __tablename__ = "worker_location_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    worker_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workers.id", ondelete="CASCADE"), index=True
    )
    location: Mapped[object] = mapped_column(Geography("POINT", srid=4326))
    accuracy_meters: Mapped[int | None] = mapped_column(Integer)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class ProviderCredential(Base):
    """Operator-verified provider qualification metadata; never stores secret documents."""

    __tablename__ = "provider_credentials"
    __table_args__ = (
        UniqueConstraint("vendor_id", "credential_type", "jurisdiction"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vendors.id", ondelete="CASCADE"), index=True
    )
    credential_type: Mapped[ProviderCredentialType] = mapped_column(
        Enum(ProviderCredentialType, name="provider_credential_type"), index=True
    )
    jurisdiction: Mapped[str] = mapped_column(String(3), index=True)
    reference_last4: Mapped[str | None] = mapped_column(String(4))
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProviderApplication(Base):
    __tablename__ = "provider_applications"
    __table_args__ = (
        UniqueConstraint("vendor_id", name="uq_provider_application_vendor"),
        CheckConstraint("version > 0", name="provider_application_positive_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[ProviderApplicationStatus] = mapped_column(
        Enum(ProviderApplicationStatus, name="provider_application_status"),
        nullable=False,
        default=ProviderApplicationStatus.DRAFT,
        index=True,
    )
    identity: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    business: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    contact_details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    services: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    skills: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    service_areas: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    postal_codes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    availability: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    capacity: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    licenses: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    insurance: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    compliance_documents: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    decision_reason: Mapped[str | None] = mapped_column(String(1000))
    requested_information: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
