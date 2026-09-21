"""provider registration and onboarding application lifecycle

Revision ID: 028_provider_onboarding
Revises: 027_access_identity_tenancy_rbac
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "028_provider_onboarding"
down_revision = "027_access_identity_tenancy_rbac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    status_type = postgresql.ENUM(
        "DRAFT",
        "PENDING",
        "INFORMATION_REQUESTED",
        "APPROVED",
        "REJECTED",
        name="provider_application_status",
        create_type=False,
    )
    op.execute(
        "CREATE TYPE provider_application_status AS ENUM "
        "('DRAFT','PENDING','INFORMATION_REQUESTED','APPROVED','REJECTED')"
    )
    op.create_table(
        "provider_applications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "vendor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vendors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", status_type, nullable=False, server_default="DRAFT"),
        sa.Column("identity", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("business", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("contact_details", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("services", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("skills", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("service_areas", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("postal_codes", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("availability", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("capacity", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("licenses", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("insurance", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("compliance_documents", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True)),
        sa.Column("decision_reason", sa.String(1000)),
        sa.Column("requested_information", sa.String(1000)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("version > 0", name="ck_provider_applications_provider_application_positive_version"),
        sa.UniqueConstraint("vendor_id", name="uq_provider_application_vendor"),
    )
    op.create_index("ix_provider_applications_vendor_id", "provider_applications", ["vendor_id"])
    op.create_index("ix_provider_applications_status", "provider_applications", ["status"])
    op.create_index("ix_provider_applications_reviewed_by", "provider_applications", ["reviewed_by"])
    op.create_index("ix_provider_applications_created_at", "provider_applications", ["created_at"])


def downgrade() -> None:
    op.drop_table("provider_applications")
    postgresql.ENUM(name="provider_application_status").drop(op.get_bind())
