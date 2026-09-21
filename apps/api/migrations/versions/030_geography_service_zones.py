"""normalize address evidence and service-zone postal routing

Revision ID: 030_geography_service_zones
Revises: 029_booking_intents
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "030_geography_service_zones"
down_revision = "029_booking_intents"
branch_labels = None
depends_on = None


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    existing = {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table_name)}
    if column.name not in existing:
        op.add_column(table_name, column)


def upgrade() -> None:
    op.add_column(
        "service_areas",
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
    )
    op.add_column(
        "service_areas",
        sa.Column(
            "emergency_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "service_areas",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_check_constraint(
        "service_area_priority_nonnegative",
        "service_areas",
        "priority >= 0",
    )
    op.create_check_constraint(
        "service_area_positive_version",
        "service_areas",
        "version > 0",
    )
    # NOTE: "service_area_radius_requires_center" is already created by migration
    # 012_service_area_dimensions with an identical predicate. This branch was
    # authored before 012 landed on main; re-creating it here raises
    # DuplicateObject. The constraint is left untouched by this migration.
    op.create_index("ix_service_areas_priority", "service_areas", ["priority"])

    _add_column_if_missing("addresses", sa.Column("line2", sa.String(200)))
    op.add_column("addresses", sa.Column("county", sa.String(120)))
    _add_column_if_missing("addresses", sa.Column("postal_code_plus4", sa.String(4)))
    op.add_column(
        "addresses",
        sa.Column(
            "validation_status",
            sa.String(32),
            nullable=False,
            server_default="VALID",
        ),
    )
    op.add_column("addresses", sa.Column("provider_reference", sa.String(255)))
    op.add_column("addresses", sa.Column("validation_confidence", sa.Numeric(5, 4)))
    op.create_check_constraint(
        "address_postal_plus4_format",
        "addresses",
        "postal_code_plus4 IS NULL OR postal_code_plus4 ~ '^[0-9]{4}$'",
    )
    op.create_check_constraint(
        "address_validation_confidence_range",
        "addresses",
        "validation_confidence IS NULL OR "
        "(validation_confidence >= 0 AND validation_confidence <= 1)",
    )
    op.create_index("ix_addresses_postal_code", "addresses", ["postal_code"])
    op.create_index("ix_addresses_state_code", "addresses", ["state_code"])
    op.create_index(
        "ix_addresses_service_area_id",
        "addresses",
        ["service_area_id"],
    )

    import_status = postgresql.ENUM(
        "PENDING",
        "COMPLETED",
        "FAILED",
        name="postal_code_import_status",
        create_type=False,
    )
    op.execute(
        "CREATE TYPE postal_code_import_status AS ENUM "
        "('PENDING','COMPLETED','FAILED')"
    )

    op.create_table(
        "service_zone_services",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "service_area_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("service_areas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "service_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("services.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "regular_service_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "emergency_service_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
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
        sa.UniqueConstraint(
            "service_area_id",
            "service_id",
            name="uq_service_zone_services_area_service",
        ),
    )
    op.create_index(
        "ix_service_zone_services_service_area_id",
        "service_zone_services",
        ["service_area_id"],
    )
    op.create_index(
        "ix_service_zone_services_service_id",
        "service_zone_services",
        ["service_id"],
    )

    op.create_table(
        "service_area_postal_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "service_area_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("service_areas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("postal_code", sa.String(10), nullable=False),
        sa.Column("city", sa.String(120)),
        sa.Column("state_code", sa.String(3)),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "regular_service_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "emergency_service_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
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
            "postal_code ~ '^[0-9]{5}(-[0-9]{4})?$'",
            name="ck_service_area_postal_codes_service_zone_postal_code_format",
        ),
        sa.CheckConstraint(
            "priority >= 0",
            name=(
                "ck_service_area_postal_codes_"
                "service_zone_postal_code_priority_nonnegative"
            ),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=(
                "ck_service_area_postal_codes_"
                "service_zone_postal_code_positive_version"
            ),
        ),
        sa.UniqueConstraint(
            "service_area_id",
            "postal_code",
            name="uq_service_area_postal_codes_area_postal",
        ),
    )
    op.create_index(
        "ix_service_area_postal_codes_service_area_id",
        "service_area_postal_codes",
        ["service_area_id"],
    )
    op.create_index(
        "ix_service_area_postal_codes_postal_code",
        "service_area_postal_codes",
        ["postal_code"],
    )
    op.create_index(
        "ix_service_area_postal_codes_city",
        "service_area_postal_codes",
        ["city"],
    )
    op.create_index(
        "ix_service_area_postal_codes_state_code",
        "service_area_postal_codes",
        ["state_code"],
    )
    op.create_index(
        "ix_service_area_postal_codes_active",
        "service_area_postal_codes",
        ["active"],
    )
    op.create_index(
        "ix_service_zone_postal_match",
        "service_area_postal_codes",
        ["postal_code", "active", "regular_service_enabled"],
    )

    op.create_table(
        "postal_code_imports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "service_area_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("service_areas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "requested_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("status", import_status, nullable=False, server_default="PENDING"),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
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
            "total_rows >= 0",
            name="ck_postal_code_imports_postal_import_total_nonnegative",
        ),
        sa.CheckConstraint(
            "imported_rows >= 0",
            name="ck_postal_code_imports_postal_import_imported_nonnegative",
        ),
        sa.CheckConstraint(
            "rejected_rows >= 0",
            name="ck_postal_code_imports_postal_import_rejected_nonnegative",
        ),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_postal_code_imports_idempotency_key",
        ),
    )
    op.create_index(
        "ix_postal_code_imports_service_area_id",
        "postal_code_imports",
        ["service_area_id"],
    )
    op.create_index(
        "ix_postal_code_imports_requested_by",
        "postal_code_imports",
        ["requested_by"],
    )
    op.create_index(
        "ix_postal_code_imports_idempotency_key",
        "postal_code_imports",
        ["idempotency_key"],
    )
    op.create_index(
        "ix_postal_code_imports_status",
        "postal_code_imports",
        ["status"],
    )

    op.execute(
        """
        INSERT INTO service_zone_services (
            id,
            service_area_id,
            service_id,
            active,
            regular_service_enabled,
            emergency_service_enabled,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            availability.service_area_id,
            availability.service_id,
            TRUE,
            TRUE,
            FALSE,
            now(),
            now()
        FROM (
            SELECT DISTINCT service_area_id, service_id
            FROM availability_rules
        ) AS availability
        ON CONFLICT (service_area_id, service_id) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO service_area_postal_codes (
            id,
            service_area_id,
            postal_code,
            city,
            state_code,
            active,
            regular_service_enabled,
            emergency_service_enabled,
            priority,
            version,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            service_area.id,
            postal.code,
            service_area.city,
            service_area.state_code,
            TRUE,
            TRUE,
            service_area.emergency_enabled,
            service_area.priority,
            1,
            now(),
            now()
        FROM service_areas AS service_area
        CROSS JOIN LATERAL jsonb_array_elements_text(
            service_area.postal_codes
        ) AS postal(code)
        WHERE postal.code ~ '^[0-9]{5}(-[0-9]{4})?$'
        ON CONFLICT (service_area_id, postal_code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("postal_code_imports")
    op.drop_table("service_area_postal_codes")
    op.drop_table("service_zone_services")
    postgresql.ENUM(name="postal_code_import_status").drop(op.get_bind())

    op.drop_index("ix_addresses_service_area_id", table_name="addresses")
    op.drop_index("ix_addresses_state_code", table_name="addresses")
    op.drop_index("ix_addresses_postal_code", table_name="addresses")
    op.drop_constraint(
        "address_validation_confidence_range",
        "addresses",
        type_="check",
    )
    op.drop_constraint(
        "address_postal_plus4_format",
        "addresses",
        type_="check",
    )
    op.drop_column("addresses", "validation_confidence")
    op.drop_column("addresses", "provider_reference")
    op.drop_column("addresses", "validation_status")
    op.drop_column("addresses", "postal_code_plus4")
    op.drop_column("addresses", "county")
    op.drop_column("addresses", "line2")

    op.drop_index("ix_service_areas_priority", table_name="service_areas")
    # "service_area_radius_requires_center" is owned by migration 012, not this one.
    op.drop_constraint(
        "service_area_positive_version",
        "service_areas",
        type_="check",
    )
    op.drop_constraint(
        "service_area_priority_nonnegative",
        "service_areas",
        type_="check",
    )
    op.drop_column("service_areas", "version")
    op.drop_column("service_areas", "emergency_enabled")
    op.drop_column("service_areas", "priority")
