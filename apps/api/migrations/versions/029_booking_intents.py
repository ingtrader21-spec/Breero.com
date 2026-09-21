"""separate pre-submission booking intents from submitted bookings

Revision ID: 029_booking_intents
Revises: 028_provider_onboarding
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "029_booking_intents"
down_revision = "028_provider_onboarding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    status_type = postgresql.ENUM(
        "DRAFT",
        "ADDRESS_VALIDATED",
        "COVERAGE_CONFIRMED",
        "AVAILABILITY_FOUND",
        "SUBMITTED",
        "EXPIRED",
        name="booking_intent_status",
        create_type=False,
    )
    op.execute(
        "CREATE TYPE booking_intent_status AS ENUM "
        "('DRAFT','ADDRESS_VALIDATED','COVERAGE_CONFIRMED',"
        "'AVAILABILITY_FOUND','SUBMITTED','EXPIRED')"
    )
    op.create_table(
        "booking_intents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("public_reference", sa.String(24), nullable=False),
        sa.Column("anonymous_session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "service_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("services.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "address_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("addresses.id", ondelete="SET NULL"),
        ),
        sa.Column("timezone_id", sa.String(64)),
        sa.Column("requested_date", sa.Date()),
        sa.Column("selected_slot", postgresql.JSONB()),
        sa.Column("status", status_type, nullable=False, server_default="DRAFT"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "booking_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bookings.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "version > 0",
            name="ck_booking_intents_booking_intent_positive_version",
        ),
        sa.CheckConstraint(
            "expires_at > created_at",
            name="ck_booking_intents_booking_intent_expiry_after_creation",
        ),
        sa.UniqueConstraint(
            "public_reference",
            name="uq_booking_intents_public_reference",
        ),
    )
    op.create_index(
        "ix_booking_intents_anonymous_session_id",
        "booking_intents",
        ["anonymous_session_id"],
    )
    op.create_index("ix_booking_intents_service_id", "booking_intents", ["service_id"])
    op.create_index("ix_booking_intents_address_id", "booking_intents", ["address_id"])
    op.create_index("ix_booking_intents_status", "booking_intents", ["status"])
    op.create_index("ix_booking_intents_expires_at", "booking_intents", ["expires_at"])
    op.create_index("ix_booking_intents_booking_id", "booking_intents", ["booking_id"])


def downgrade() -> None:
    op.drop_table("booking_intents")
    postgresql.ENUM(name="booking_intent_status").drop(op.get_bind())
