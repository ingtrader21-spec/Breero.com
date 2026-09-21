import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class SkillDefinition(Base):
    """BREERO-owned skill catalog; providers may select, never invent, skills."""

    __tablename__ = "skill_definitions"
    __table_args__ = (
        CheckConstraint("version > 0", name="skill_definition_positive_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(
        String(100), nullable=False, default="home-services", index=True
    )
    description: Mapped[str | None] = mapped_column(Text)
    provider_approval_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ServiceSkillRequirement(Base):
    """Hard skill qualification attached to one BREERO catalog service."""

    __tablename__ = "service_skill_requirements"
    __table_args__ = (
        UniqueConstraint(
            "service_id",
            "skill_id",
            name="uq_service_skill_requirements_service_skill",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skill_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProviderService(Base):
    __tablename__ = "provider_catalog_services"
    __table_args__ = (
        UniqueConstraint(
            "vendor_id",
            "service_id",
            name="uq_provider_catalog_services_vendor_service",
        ),
        CheckConstraint("version > 0", name="provider_service_positive_version"),
        CheckConstraint(
            "display_order >= 0",
            name="provider_service_display_order_nonnegative",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("services.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus, name="provider_catalog_approval_status", native_enum=True),
        nullable=False,
        default=ApprovalStatus.PENDING,
        index=True,
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ProviderSkill(Base):
    __tablename__ = "provider_catalog_skills"
    __table_args__ = (
        UniqueConstraint(
            "worker_id",
            "skill_id",
            name="uq_provider_catalog_skills_worker_skill",
        ),
        CheckConstraint("version > 0", name="provider_skill_positive_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    worker_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skill_definitions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(
            ApprovalStatus,
            name="provider_catalog_approval_status",
            native_enum=True,
            create_type=False,
        ),
        nullable=False,
        default=ApprovalStatus.PENDING,
        index=True,
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
