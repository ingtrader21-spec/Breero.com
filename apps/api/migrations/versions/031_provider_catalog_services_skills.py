"""normalize provider service and professional skill selections

Revision ID: 031_provider_catalog
Revises: 030_geography_service_zones
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "031_provider_catalog"
down_revision = "030_geography_service_zones"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "services",
        sa.Column(
            "provider_approval_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )

    approval_status = postgresql.ENUM(
        "PENDING",
        "APPROVED",
        "REJECTED",
        name="provider_catalog_approval_status",
        create_type=False,
    )
    op.execute(
        "CREATE TYPE provider_catalog_approval_status AS ENUM "
        "('PENDING','APPROVED','REJECTED')"
    )

    op.create_table(
        "skill_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column(
            "category",
            sa.String(100),
            nullable=False,
            server_default="home-services",
        ),
        sa.Column("description", sa.Text()),
        sa.Column(
            "provider_approval_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
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
            "version > 0",
            name="ck_skill_definitions_skill_definition_positive_version",
        ),
        sa.UniqueConstraint("key", name="uq_skill_definitions_key"),
    )
    op.create_index("ix_skill_definitions_key", "skill_definitions", ["key"])
    op.create_index(
        "ix_skill_definitions_category",
        "skill_definitions",
        ["category"],
    )
    op.create_index(
        "ix_skill_definitions_active",
        "skill_definitions",
        ["active"],
    )

    op.create_table(
        "service_skill_requirements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "service_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("services.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "skill_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("skill_definitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "service_id",
            "skill_id",
            name="uq_service_skill_requirements_service_skill",
        ),
    )
    op.create_index(
        "ix_service_skill_requirements_service_id",
        "service_skill_requirements",
        ["service_id"],
    )
    op.create_index(
        "ix_service_skill_requirements_skill_id",
        "service_skill_requirements",
        ["skill_id"],
    )

    op.create_table(
        "provider_catalog_services",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "vendor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vendors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "service_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("services.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status",
            approval_status,
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "reviewed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("rejection_reason", sa.String(1000)),
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
            name="ck_provider_catalog_services_provider_service_positive_version",
        ),
        sa.CheckConstraint(
            "display_order >= 0",
            name="ck_provider_catalog_services_provider_service_display_order_nonnegative",
        ),
        sa.UniqueConstraint(
            "vendor_id",
            "service_id",
            name="uq_provider_catalog_services_vendor_service",
        ),
    )
    op.create_index("ix_provider_catalog_services_vendor_id", "provider_catalog_services", ["vendor_id"])
    op.create_index("ix_provider_catalog_services_service_id", "provider_catalog_services", ["service_id"])
    op.create_index("ix_provider_catalog_services_status", "provider_catalog_services", ["status"])
    op.create_index("ix_provider_catalog_services_active", "provider_catalog_services", ["active"])
    op.create_index("ix_provider_catalog_services_reviewed_by", "provider_catalog_services", ["reviewed_by"])

    op.create_table(
        "provider_catalog_skills",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "vendor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vendors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "worker_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "skill_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("skill_definitions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status",
            approval_status,
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "reviewed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("rejection_reason", sa.String(1000)),
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
            name="ck_provider_catalog_skills_provider_skill_positive_version",
        ),
        sa.UniqueConstraint(
            "worker_id",
            "skill_id",
            name="uq_provider_catalog_skills_worker_skill",
        ),
    )
    op.create_index("ix_provider_catalog_skills_vendor_id", "provider_catalog_skills", ["vendor_id"])
    op.create_index("ix_provider_catalog_skills_worker_id", "provider_catalog_skills", ["worker_id"])
    op.create_index("ix_provider_catalog_skills_skill_id", "provider_catalog_skills", ["skill_id"])
    op.create_index("ix_provider_catalog_skills_status", "provider_catalog_skills", ["status"])
    op.create_index("ix_provider_catalog_skills_active", "provider_catalog_skills", ["active"])
    op.create_index("ix_provider_catalog_skills_reviewed_by", "provider_catalog_skills", ["reviewed_by"])

    op.execute(
        """
        INSERT INTO role_permissions (id, role_key, permission, allow)
        SELECT gen_random_uuid(), permission.role_key, permission.permission, TRUE
        FROM (
            VALUES
                ('vendor_admin', 'provider.services.read'),
                ('vendor_admin', 'provider.services.manage'),
                ('vendor_admin', 'provider.skills.read'),
                ('vendor_admin', 'provider.skills.manage'),
                ('technician', 'provider.services.read'),
                ('technician', 'provider.skills.read')
        ) AS permission(role_key, permission)
        ON CONFLICT (role_key, permission) DO NOTHING
        """
    )

    op.execute(
        """
        WITH raw_skills AS (
            SELECT jsonb_array_elements_text(application.skills) AS value
            FROM provider_applications AS application
            WHERE jsonb_typeof(application.skills) = 'array'
            UNION
            SELECT jsonb_array_elements_text(worker.skills) AS value
            FROM workers AS worker
            WHERE jsonb_typeof(worker.skills) = 'array'
        ),
        normalized AS (
            SELECT DISTINCT ON (skill_key)
                skill_key,
                left(trim(value), 160) AS skill_name
            FROM (
                SELECT
                    value,
                    btrim(
                        regexp_replace(
                            lower(trim(value)),
                            '[^a-z0-9]+',
                            '-',
                            'g'
                        ),
                        '-'
                    ) AS skill_key
                FROM raw_skills
            ) AS skill
            WHERE skill_key <> ''
            ORDER BY skill_key, skill_name
        )
        INSERT INTO skill_definitions (
            id,
            key,
            name,
            category,
            provider_approval_required,
            active,
            version,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            skill_key,
            skill_name,
            'legacy-import',
            TRUE,
            TRUE,
            1,
            now(),
            now()
        FROM normalized
        ON CONFLICT (key) DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO provider_catalog_services (
            id,
            vendor_id,
            service_id,
            status,
            active,
            display_order,
            version,
            created_at,
            updated_at
        )
        SELECT DISTINCT ON (application.vendor_id, service.id)
            gen_random_uuid(),
            application.vendor_id,
            service.id,
            CASE
                WHEN application.status::text = 'APPROVED'
                    THEN 'APPROVED'::provider_catalog_approval_status
                ELSE 'PENDING'::provider_catalog_approval_status
            END,
            TRUE,
            0,
            1,
            now(),
            now()
        FROM provider_applications AS application
        CROSS JOIN LATERAL jsonb_array_elements_text(application.services) item(value)
        JOIN services AS service
          ON service.id::text = item.value
          OR service.slug = item.value
        WHERE jsonb_typeof(application.services) = 'array'
        ON CONFLICT (vendor_id, service_id) DO NOTHING
        """
    )

    op.execute(
        """
        WITH application_skills AS (
            SELECT
                application.vendor_id,
                application.status AS application_status,
                item.value,
                btrim(
                    regexp_replace(
                        lower(trim(item.value)),
                        '[^a-z0-9]+',
                        '-',
                        'g'
                    ),
                    '-'
                ) AS skill_key
            FROM provider_applications AS application
            CROSS JOIN LATERAL jsonb_array_elements_text(application.skills) item(value)
            WHERE jsonb_typeof(application.skills) = 'array'
        )
        INSERT INTO provider_catalog_skills (
            id,
            vendor_id,
            worker_id,
            skill_id,
            status,
            active,
            version,
            created_at,
            updated_at
        )
        SELECT DISTINCT ON (worker.id, skill.id)
            gen_random_uuid(),
            source.vendor_id,
            worker.id,
            skill.id,
            CASE
                WHEN source.application_status::text = 'APPROVED'
                    THEN 'APPROVED'::provider_catalog_approval_status
                ELSE 'PENDING'::provider_catalog_approval_status
            END,
            TRUE,
            1,
            now(),
            now()
        FROM application_skills AS source
        JOIN skill_definitions AS skill ON skill.key = source.skill_key
        JOIN LATERAL (
            SELECT professional.id
            FROM workers AS professional
            JOIN vendors AS vendor ON vendor.id = professional.vendor_id
            WHERE professional.vendor_id = source.vendor_id
            ORDER BY
                (professional.user_id = vendor.owner_user_id) DESC,
                professional.created_at,
                professional.id
            LIMIT 1
        ) AS worker ON TRUE
        WHERE source.skill_key <> ''
        ON CONFLICT (worker_id, skill_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE (role_key, permission) IN (
            ('vendor_admin', 'provider.services.read'),
            ('vendor_admin', 'provider.services.manage'),
            ('vendor_admin', 'provider.skills.read'),
            ('vendor_admin', 'provider.skills.manage'),
            ('technician', 'provider.services.read'),
            ('technician', 'provider.skills.read')
        )
        """
    )
    op.drop_table("provider_catalog_skills")
    op.drop_table("provider_catalog_services")
    op.drop_table("service_skill_requirements")
    op.drop_table("skill_definitions")
    postgresql.ENUM(name="provider_catalog_approval_status").drop(op.get_bind())
    op.drop_column("services", "provider_approval_required")
