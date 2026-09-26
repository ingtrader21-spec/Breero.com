import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class QualificationType(str, enum.Enum):
    LICENSE = "LICENSE"
    INSURANCE = "INSURANCE"
    CERTIFICATION = "CERTIFICATION"
    BACKGROUND_CHECK = "BACKGROUND_CHECK"
    TRAINING = "TRAINING"
    OTHER = "OTHER"


class QualificationStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    WITHDRAWN = "WITHDRAWN"


class QualificationReviewStatus(str, enum.Enum):
    NOT_SUBMITTED = "NOT_SUBMITTED"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    INFORMATION_REQUESTED = "INFORMATION_REQUESTED"


class ProviderQualification(Base):
    """Provider-declared qualification metadata awaiting BREERO review.

    This is deliberately separate from ``provider_credentials``: those rows are the
    operator-verified booking authority. Nothing here is trusted for scheduling until a
    reviewer promotes it. Only a masked reference and an opaque evidence reference are
    kept; document binaries are never stored in this table.
    """

    __tablename__ = "provider_qualifications"
    __table_args__ = (
        CheckConstraint("version > 0", name="provider_qualification_positive_version"),
        CheckConstraint(
            "issued_on IS NULL OR expires_on IS NULL OR issued_on <= expires_on",
            name="provider_qualification_date_order",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    worker_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workers.id", ondelete="CASCADE"), index=True
    )
    qualification_type: Mapped[QualificationType] = mapped_column(
        Enum(QualificationType, name="provider_qualification_type"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    issuer: Mapped[str | None] = mapped_column(String(160))
    jurisdiction: Mapped[str | None] = mapped_column(String(3))
    reference_last4: Mapped[str | None] = mapped_column(String(4))
    issued_on: Mapped[date | None] = mapped_column(Date)
    expires_on: Mapped[date | None] = mapped_column(Date, index=True)
    evidence_reference: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[QualificationStatus] = mapped_column(
        Enum(QualificationStatus, name="provider_qualification_status"),
        nullable=False,
        default=QualificationStatus.DRAFT,
        index=True,
    )
    review_status: Mapped[QualificationReviewStatus] = mapped_column(
        Enum(QualificationReviewStatus, name="provider_qualification_review_status"),
        nullable=False,
        default=QualificationReviewStatus.NOT_SUBMITTED,
        index=True,
    )
    review_reason: Mapped[str | None] = mapped_column(String(1000))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
