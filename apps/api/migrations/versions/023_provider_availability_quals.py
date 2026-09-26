"""provider-declared availability, blackout periods, and qualification metadata

Revision ID: 023_provider_availability_quals
Revises: 022_provider_services_skills
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# alembic_version.version_num is VARCHAR(32); keep revision identifiers within it.
revision = "023_provider_availability_quals"
down_revision = "022_provider_services_skills"
branch_labels = None
depends_on = None

QUALIFICATION_TYPES = (
    "LICENSE",
    "INSURANCE",
    "CERTIFICATION",
    "BACKGROUND_CHECK",
    "TRAINING",
    "OTHER",
)
QUALIFICATION_STATUSES = ("DRAFT", "SUBMITTED", "WITHDRAWN")
QUALIFICATION_REVIEW_STATUSES = (
    "NOT_SUBMITTED",
    "PENDING_REVIEW",
    "APPROVED",
    "REJECTED",
    "INFORMATION_REQUESTED",
)


def _timestamps() -> list[sa.Column]:
    return [
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
    ]


def _owner_columns() -> list[sa.Column]:
    return [
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
            nullable=True,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "provider_availability_rules",
        *_owner_columns(),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        *_timestamps(),
        sa.CheckConstraint(
            "weekday >= 0 AND weekday <= 6",
            name="ck_provider_availability_rules_availability_rule_weekday_range",
        ),
        sa.CheckConstraint(
            "start_time < end_time",
            name="ck_provider_availability_rules_availability_rule_time_order",
        ),
        sa.CheckConstraint(
            "valid_from IS NULL OR valid_until IS NULL OR valid_from <= valid_until",
            name="ck_provider_availability_rules_availability_rule_date_order",
        ),
        sa.CheckConstraint(
            "version > 0",
            name="ck_provider_availability_rules_availability_rule_positive_version",
        ),
    )
    op.create_index(
        "ix_provider_availability_rules_vendor_id",
        "provider_availability_rules",
        ["vendor_id"],
    )
    op.create_index(
        "ix_provider_availability_rules_worker_id",
        "provider_availability_rules",
        ["worker_id"],
    )
    op.create_index(
        "ix_provider_availability_rules_active",
        "provider_availability_rules",
        ["active"],
    )

    op.create_table(
        "provider_blackout_periods",
        *_owner_columns(),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        *_timestamps(),
        sa.CheckConstraint(
            "starts_at < ends_at",
            name="ck_provider_blackout_periods_blackout_period_time_order",
        ),
        sa.CheckConstraint(
            "version > 0",
            name="ck_provider_blackout_periods_blackout_period_positive_version",
        ),
    )
    op.create_index(
        "ix_provider_blackout_periods_vendor_id",
        "provider_blackout_periods",
        ["vendor_id"],
    )
    op.create_index(
        "ix_provider_blackout_periods_worker_id",
        "provider_blackout_periods",
        ["worker_id"],
    )
    op.create_index(
        "ix_provider_blackout_periods_starts_at",
        "provider_blackout_periods",
        ["starts_at"],
    )
    op.create_index(
        "ix_provider_blackout_periods_active",
        "provider_blackout_periods",
        ["active"],
    )

    qualification_type = postgresql.ENUM(
        *QUALIFICATION_TYPES, name="provider_qualification_type", create_type=False
    )
    qualification_status = postgresql.ENUM(
        *QUALIFICATION_STATUSES, name="provider_qualification_status", create_type=False
    )
    review_status = postgresql.ENUM(
        *QUALIFICATION_REVIEW_STATUSES,
        name="provider_qualification_review_status",
        create_type=False,
    )
    bind = op.get_bind()
    qualification_type.create(bind, checkfirst=False)
    qualification_status.create(bind, checkfirst=False)
    review_status.create(bind, checkfirst=False)

    op.create_table(
        "provider_qualifications",
        *_owner_columns(),
        sa.Column("qualification_type", qualification_type, nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("issuer", sa.String(160), nullable=True),
        sa.Column("jurisdiction", sa.String(3), nullable=True),
        sa.Column("reference_last4", sa.String(4), nullable=True),
        sa.Column("issued_on", sa.Date(), nullable=True),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("evidence_reference", sa.String(128), nullable=True),
        sa.Column(
            "status",
            qualification_status,
            nullable=False,
            server_default="DRAFT",
        ),
        sa.Column(
            "review_status",
            review_status,
            nullable=False,
            server_default="NOT_SUBMITTED",
        ),
        sa.Column("review_reason", sa.String(1000), nullable=True),
        sa.Column(
            "reviewed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        *_timestamps(),
        sa.CheckConstraint(
            "version > 0",
            name="ck_provider_qualifications_provider_qualification_positive_version",
        ),
        sa.CheckConstraint(
            "issued_on IS NULL OR expires_on IS NULL OR issued_on <= expires_on",
            name="ck_provider_qualifications_provider_qualification_date_order",
        ),
    )
    for column in (
        "vendor_id",
        "worker_id",
        "qualification_type",
        "expires_on",
        "status",
        "review_status",
    ):
        op.create_index(
            f"ix_provider_qualifications_{column}",
            "provider_qualifications",
            [column],
        )

    op.execute(
        """
        INSERT INTO role_permissions (id, role_key, permission, allow)
        SELECT gen_random_uuid(), permission.role_key, permission.permission, TRUE
        FROM (
            VALUES
                ('vendor_admin', 'provider.availability.read'),
                ('vendor_admin', 'provider.qualifications.manage'),
                ('vendor_admin', 'provider.offers.decide')
        ) AS permission(role_key, permission)
        ON CONFLICT (role_key, permission) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE (role_key, permission) IN (
            ('vendor_admin', 'provider.availability.read'),
            ('vendor_admin', 'provider.qualifications.manage'),
            ('vendor_admin', 'provider.offers.decide')
        )
        """
    )
    op.drop_table("provider_qualifications")
    op.drop_table("provider_blackout_periods")
    op.drop_table("provider_availability_rules")
    bind = op.get_bind()
    postgresql.ENUM(name="provider_qualification_review_status").drop(bind)
    postgresql.ENUM(name="provider_qualification_status").drop(bind)
    postgresql.ENUM(name="provider_qualification_type").drop(bind)
