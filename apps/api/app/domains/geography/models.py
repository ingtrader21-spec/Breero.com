import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domains.common.models import TimestampMixin, UUIDPrimaryKeyMixin


class PostalCodeImportStatus(str, enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ServiceZoneOffering(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Service catalog eligibility inside one BREERO-controlled service zone."""

    __tablename__ = "service_zone_services"
    __table_args__ = (
        UniqueConstraint(
            "service_area_id",
            "service_id",
            name="uq_service_zone_services_area_service",
        ),
    )

    service_area_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("service_areas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    regular_service_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    emergency_service_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )


class ServiceZonePostalCode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Normalized postal coverage owned by a BREERO service zone."""

    __tablename__ = "service_area_postal_codes"
    __table_args__ = (
        UniqueConstraint(
            "service_area_id",
            "postal_code",
            name="uq_service_area_postal_codes_area_postal",
        ),
        CheckConstraint(
            "postal_code ~ '^[0-9]{5}(-[0-9]{4})?$'",
            name="service_zone_postal_code_format",
        ),
        CheckConstraint(
            "priority >= 0",
            name="service_zone_postal_code_priority_nonnegative",
        ),
        CheckConstraint(
            "version > 0",
            name="service_zone_postal_code_positive_version",
        ),
        Index(
            "ix_service_zone_postal_match",
            "postal_code",
            "active",
            "regular_service_enabled",
        ),
    )

    service_area_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("service_areas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    postal_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    city: Mapped[str | None] = mapped_column(String(120), index=True)
    state_code: Mapped[str | None] = mapped_column(String(3), index=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    regular_service_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    emergency_service_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class PostalCodeImport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Durable evidence for bounded administrative postal-code imports."""

    __tablename__ = "postal_code_imports"
    __table_args__ = (
        CheckConstraint("total_rows >= 0", name="postal_import_total_nonnegative"),
        CheckConstraint("imported_rows >= 0", name="postal_import_imported_nonnegative"),
        CheckConstraint("rejected_rows >= 0", name="postal_import_rejected_nonnegative"),
    )

    service_area_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("service_areas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        unique=True,
        index=True,
    )
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[PostalCodeImportStatus] = mapped_column(
        Enum(
            PostalCodeImportStatus,
            name="postal_code_import_status",
            native_enum=True,
        ),
        nullable=False,
        default=PostalCodeImportStatus.PENDING,
        index=True,
    )
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
