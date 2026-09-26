import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domains.common.models import TimestampMixin, UUIDPrimaryKeyMixin


class EventStatus(str, enum.Enum):
    PENDING = "PENDING"
    PENDING_CONFIGURATION = "PENDING_CONFIGURATION"
    PROCESSING = "PROCESSING"
    DELIVERED = "DELIVERED"
    RETRYING = "RETRYING"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_TERMINAL = "FAILED_TERMINAL"
    # Legacy values remain readable during the rolling schema upgrade.
    FAILED = "FAILED"
    DEAD_LETTER = "DEAD_LETTER"


class IntegrationEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "integration_events"
    aggregate_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    aggregate_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[EventStatus] = mapped_column(
        Enum(EventStatus, name="integration_event_status"), default=EventStatus.PENDING, index=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    claim_token: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    external_model: Mapped[str | None] = mapped_column(String(120))
    external_record_id: Mapped[str | None] = mapped_column(String(120))

    @property
    def attempts(self):
        return self.attempt_count

    @attempts.setter
    def attempts(self, value):
        self.attempt_count = value

    @property
    def available_at(self):
        return self.next_attempt_at

    @available_at.setter
    def available_at(self, value):
        self.next_attempt_at = value

    @property
    def delivered_at(self):
        return self.processed_at

    @delivered_at.setter
    def delivered_at(self, value):
        self.processed_at = value


class AuditLog(UUIDPrimaryKeyMixin, Base):
    """Append-only audit record; read through app.domains.audit, never serialized raw."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        CheckConstraint(
            "result IN ('success', 'denied', 'failure')",
            name="ck_audit_logs_result",
        ),
        Index("ix_audit_logs_created_at_id", text("created_at DESC"), text("id DESC")),
        Index("ix_audit_logs_actor_created", "actor_id", text("created_at DESC")),
        Index(
            "ix_audit_logs_action_created",
            "action",
            "created_at",
            postgresql_ops={"action": "varchar_pattern_ops"},
        ),
        Index(
            "ix_audit_logs_resource_created",
            "resource_type",
            "resource_id",
            text("created_at DESC"),
        ),
        Index(
            "ix_audit_logs_correlation_created",
            "correlation_id",
            "created_at",
            postgresql_where=text("correlation_id IS NOT NULL"),
        ),
        Index(
            "ix_audit_logs_result_created",
            "result",
            text("created_at DESC"),
            postgresql_where=text("result <> 'success'"),
        ),
        Index(
            "ix_audit_logs_vendor_created",
            "vendor_id",
            text("created_at DESC"),
            postgresql_where=text("vendor_id IS NOT NULL"),
        ),
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Read-model context (023_audit_read_model). Populated from the request context by
    # app.domains.audit.enrichment; historical rows keep NULL context and result=success.
    result: Mapped[str] = mapped_column(
        String(16), nullable=False, default="success", server_default="success"
    )
    request_id: Mapped[str | None] = mapped_column(String(128))
    correlation_id: Mapped[str | None] = mapped_column(String(128))
    source_ip_hash: Mapped[str | None] = mapped_column(String(64))
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


# Register insert-time audit enrichment wherever AuditLog is mapped (API, workers, scripts).
from app.domains.audit import enrichment as _audit_enrichment  # noqa: E402,F401,I001
