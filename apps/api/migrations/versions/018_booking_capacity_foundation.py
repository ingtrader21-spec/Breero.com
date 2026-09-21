"""booking capacity and service-zone foundation

Revision ID: 018_booking_capacity_foundation
Revises: 017_provider_credentials
"""

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

revision = "018_booking_capacity_foundation"
down_revision = "017_provider_credentials"
branch_labels = None
depends_on = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    ]


def upgrade() -> None:
    for value in ("UNDER_REVIEW", "PAUSED", "OFFBOARDED"):
        op.execute(f"ALTER TYPE vendor_status ADD VALUE IF NOT EXISTS '{value}'")
    op.execute("CREATE TYPE capacity_hold_status AS ENUM ('HELD','CONVERTED','EXPIRED','RELEASED')")
    op.execute(
        "CREATE TYPE availability_exception_reason AS ENUM ('VACATION','SICK','PERSONAL','TRAINING','VEHICLE','HOLIDAY','MANUAL_BLOCK','OTHER')"
    )
    op.execute("CREATE TYPE assignment_method AS ENUM ('MANUAL','SUGGESTED','AUTOMATIC')")

    op.create_table(
        "service_zones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        *timestamps(),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("state", sa.String(3)),
        sa.Column("county", sa.String(120)),
        sa.Column("city", sa.String(120)),
        sa.Column("postal_code", sa.String(5)),
        sa.Column("postal_prefix", sa.String(5)),
        sa.Column("timezone_id", sa.String(64)),
        sa.Column("center", Geometry("POINT", srid=4326)),
        sa.Column("radius_meters", sa.Integer),
        sa.Column("boundary", Geometry("MULTIPOLYGON", srid=4326)),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("regular_service_enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "emergency_service_enabled", sa.Boolean, nullable=False, server_default=sa.false()
        ),
    )
    for column in ("state", "county", "city", "postal_code", "postal_prefix", "active"):
        op.create_index(f"ix_service_zones_{column}", "service_zones", [column])
    op.create_table(
        "service_zone_postal_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        *timestamps(),
        sa.Column(
            "service_zone_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("service_zones.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("postal_code", sa.String(5), nullable=False),
        sa.Column("city", sa.String(120)),
        sa.Column("state", sa.String(3), nullable=False),
        sa.Column("county", sa.String(120)),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("priority", sa.Integer, nullable=False, server_default="100"),
        sa.UniqueConstraint("service_zone_id", "postal_code"),
    )
    op.create_index(
        "ix_service_zone_postal_codes_zone", "service_zone_postal_codes", ["service_zone_id"]
    )
    op.create_index(
        "ix_service_zone_postal_codes_lookup",
        "service_zone_postal_codes",
        ["postal_code", "state", "active", "priority"],
    )

    for name, column in (
        ("line2", sa.Column("line2", sa.String(200))),
        ("postal_code_plus4", sa.Column("postal_code_plus4", sa.String(4))),
        (
            "timezone_source",
            sa.Column("timezone_source", sa.String(40), nullable=False, server_default="geocoding"),
        ),
        (
            "address_validation_status",
            sa.Column(
                "address_validation_status",
                sa.String(32),
                nullable=False,
                server_default="VALIDATED",
            ),
        ),
        (
            "service_zone_id",
            sa.Column(
                "service_zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("service_zones.id")
            ),
        ),
    ):
        op.add_column("addresses", column)
    op.create_index("ix_addresses_service_zone_id", "addresses", ["service_zone_id"])
    op.create_index("ix_addresses_postal_state", "addresses", ["postal_code", "state_code"])

    service_columns = (
        sa.Column("before_buffer_minutes", sa.Integer, nullable=False, server_default="0"),
        sa.Column("after_buffer_minutes", sa.Integer, nullable=False, server_default="0"),
        sa.Column("emergency_eligible", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column(
            "sunday_emergency_eligible", sa.Boolean, nullable=False, server_default=sa.false()
        ),
        sa.Column("quote_required", sa.Boolean, nullable=False, server_default=sa.true()),
    )
    for column in service_columns:
        op.add_column("services", column)

    user_columns = (
        sa.Column("phone", sa.String(32)),
        sa.Column("status", sa.String(24), nullable=False, server_default="ACTIVE"),
        sa.Column("email_verified_at", sa.DateTime(timezone=True)),
        sa.Column("phone_verified_at", sa.DateTime(timezone=True)),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
    )
    for column in user_columns:
        op.add_column("users", column)
    op.create_index("ix_users_phone", "users", ["phone"])
    op.execute("CREATE UNIQUE INDEX uq_users_normalized_email ON users (lower(email))")
    op.add_column(
        "customers",
        sa.Column("preferred_language", sa.String(12), nullable=False, server_default="en-US"),
    )
    op.add_column("customers", sa.Column("default_address_id", postgresql.UUID(as_uuid=True)))

    vendor_columns = (
        sa.Column("provider_type", sa.String(32), nullable=False, server_default="COMPANY"),
        sa.Column("business_address", sa.String(240)),
        sa.Column("city", sa.String(120)),
        sa.Column("state", sa.String(3)),
        sa.Column("postal_code", sa.String(10)),
        sa.Column("onboarding_status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("compliance_status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("timezone_id", sa.String(64)),
    )
    for column in vendor_columns:
        op.add_column("vendors", column)
    worker_columns = (
        sa.Column("default_timezone_id", sa.String(64)),
        sa.Column("maximum_jobs_per_day", sa.Integer, nullable=False, server_default="6"),
        sa.Column("maximum_minutes_per_day", sa.Integer, nullable=False, server_default="600"),
        sa.Column(
            "sunday_emergency_enabled", sa.Boolean, nullable=False, server_default=sa.false()
        ),
    )
    for column in worker_columns:
        op.add_column("workers", column)

    booking_columns = (
        sa.Column("service_timezone_id", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column(
            "recommended_provider_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vendors.id")
        ),
        sa.Column(
            "recommended_professional_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workers.id"),
        ),
        sa.Column("assignment_score", sa.Integer),
        sa.Column("assignment_reason", sa.String(500)),
    )
    for column in booking_columns:
        op.add_column("bookings", column)
    op.create_index("ix_bookings_recommended_provider_id", "bookings", ["recommended_provider_id"])
    op.create_index(
        "ix_bookings_recommended_professional_id", "bookings", ["recommended_professional_id"]
    )
    op.create_index(
        "ix_bookings_status_window", "bookings", ["status", "window_start", "window_end"]
    )

    op.create_table(
        "provider_availability_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        *timestamps(),
        sa.Column(
            "provider_professional_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("day_of_week", sa.Integer, nullable=False),
        sa.Column("start_local_time", sa.Time, nullable=False),
        sa.Column("end_local_time", sa.Time, nullable=False),
        sa.Column("available", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("emergency_only", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("timezone_id", sa.String(64), nullable=False),
        sa.CheckConstraint("day_of_week BETWEEN 0 AND 6", name="availability_rule_weekday"),
        sa.CheckConstraint(
            "start_local_time >= TIME '07:00' AND end_local_time <= TIME '19:00'",
            name="availability_rule_breero_hours",
        ),
        sa.CheckConstraint("end_local_time > start_local_time", name="availability_rule_range"),
        sa.UniqueConstraint(
            "provider_professional_id", "day_of_week", "start_local_time", "end_local_time"
        ),
    )
    op.create_index(
        "ix_provider_availability_rules_professional",
        "provider_availability_rules",
        ["provider_professional_id", "day_of_week"],
    )
    op.create_table(
        "provider_availability_exceptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        *timestamps(),
        sa.Column(
            "provider_professional_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone_id", sa.String(64), nullable=False),
        sa.Column(
            "reason",
            postgresql.ENUM(name="availability_exception_reason", create_type=False),
            nullable=False,
        ),
        sa.Column("status", sa.String(24), nullable=False, server_default="ACTIVE"),
        sa.Column(
            "created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.CheckConstraint("end_at > start_at", name="availability_exception_range"),
    )
    op.create_index(
        "ix_provider_availability_exceptions_interval",
        "provider_availability_exceptions",
        ["provider_professional_id", "start_at", "end_at"],
    )
    op.create_table(
        "provider_capacity_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        *timestamps(),
        sa.Column(
            "provider_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vendors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "professional_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workers.id", ondelete="CASCADE"),
        ),
        sa.Column("max_jobs_daily", sa.Integer, nullable=False),
        sa.Column("max_minutes_daily", sa.Integer, nullable=False),
        sa.Column("max_concurrent_jobs", sa.Integer, nullable=False, server_default="1"),
        sa.Column("emergency_reserved_jobs", sa.Integer, nullable=False, server_default="0"),
        sa.Column("emergency_reserved_minutes", sa.Integer, nullable=False, server_default="0"),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("effective_until", sa.Date),
        sa.CheckConstraint(
            "max_jobs_daily > 0 AND max_minutes_daily > 0 AND max_concurrent_jobs > 0",
            name="capacity_positive",
        ),
    )
    op.create_index(
        "ix_provider_capacity_rules_lookup",
        "provider_capacity_rules",
        ["provider_id", "professional_id", "effective_from", "effective_until"],
    )
    op.create_table(
        "booking_capacity_holds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "booking_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bookings.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "provider_candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vendors.id"),
            nullable=False,
        ),
        sa.Column(
            "professional_candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workers.id"),
            nullable=False,
        ),
        sa.Column("slot_start_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("slot_end_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone_id", sa.String(64), nullable=False),
        sa.Column("capacity_minutes", sa.Integer, nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(name="capacity_hold_status", create_type=False),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("released_at", sa.DateTime(timezone=True)),
        sa.Column("converted_at", sa.DateTime(timezone=True)),
        sa.Column("owner_fingerprint_hash", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False, unique=True),
        sa.CheckConstraint("slot_end_utc > slot_start_utc", name="capacity_hold_range"),
        sa.CheckConstraint("capacity_minutes > 0", name="capacity_hold_minutes"),
    )
    op.create_index(
        "ix_capacity_holds_active_lookup",
        "booking_capacity_holds",
        ["professional_candidate_id", "status", "expires_at", "slot_start_utc", "slot_end_utc"],
    )
    op.create_index(
        "ix_capacity_holds_owner",
        "booking_capacity_holds",
        ["owner_fingerprint_hash", "status", "expires_at"],
    )
    op.create_table(
        "provider_assignment_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "booking_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bookings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "previous_provider_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vendors.id")
        ),
        sa.Column("new_provider_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vendors.id")),
        sa.Column(
            "previous_professional_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workers.id")
        ),
        sa.Column(
            "new_professional_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workers.id")
        ),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column(
            "assignment_method",
            postgresql.ENUM(name="assignment_method", create_type=False),
            nullable=False,
        ),
        sa.Column("score_at_assignment", sa.Integer),
        sa.Column(
            "performed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_provider_assignment_history_booking",
        "provider_assignment_history",
        ["booking_id", "timestamp"],
    )


def downgrade() -> None:
    op.drop_table("provider_assignment_history")
    op.drop_table("booking_capacity_holds")
    op.drop_table("provider_capacity_rules")
    op.drop_table("provider_availability_exceptions")
    op.drop_table("provider_availability_rules")
    for index in (
        "ix_bookings_status_window",
        "ix_bookings_recommended_professional_id",
        "ix_bookings_recommended_provider_id",
    ):
        op.drop_index(index, table_name="bookings")
    for column in (
        "assignment_reason",
        "assignment_score",
        "recommended_professional_id",
        "recommended_provider_id",
        "service_timezone_id",
    ):
        op.drop_column("bookings", column)
    for column in (
        "sunday_emergency_enabled",
        "maximum_minutes_per_day",
        "maximum_jobs_per_day",
        "default_timezone_id",
    ):
        op.drop_column("workers", column)
    for column in (
        "timezone_id",
        "compliance_status",
        "onboarding_status",
        "postal_code",
        "state",
        "city",
        "business_address",
        "provider_type",
    ):
        op.drop_column("vendors", column)
    for column in ("default_address_id", "preferred_language"):
        op.drop_column("customers", column)
    op.drop_index("uq_users_normalized_email", table_name="users")
    op.drop_index("ix_users_phone", table_name="users")
    for column in ("last_login_at", "phone_verified_at", "email_verified_at", "status", "phone"):
        op.drop_column("users", column)
    for column in (
        "quote_required",
        "sunday_emergency_eligible",
        "emergency_eligible",
        "after_buffer_minutes",
        "before_buffer_minutes",
    ):
        op.drop_column("services", column)
    op.drop_index("ix_addresses_postal_state", table_name="addresses")
    op.drop_index("ix_addresses_service_zone_id", table_name="addresses")
    for column in (
        "service_zone_id",
        "address_validation_status",
        "timezone_source",
        "postal_code_plus4",
        "line2",
    ):
        op.drop_column("addresses", column)
    op.drop_table("service_zone_postal_codes")
    op.drop_table("service_zones")
    postgresql.ENUM(name="assignment_method").drop(op.get_bind())
    postgresql.ENUM(name="availability_exception_reason").drop(op.get_bind())
    postgresql.ENUM(name="capacity_hold_status").drop(op.get_bind())
