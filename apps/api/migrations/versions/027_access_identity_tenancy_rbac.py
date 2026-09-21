"""identity links, tenant-aware access, permission overrides and invitations

Revision ID: 018_auth_identity_tenancy_rbac
Revises: 017_provider_credentials
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "027_access_identity_tenancy_rbac"
down_revision = "026_keycloak_identity_link"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "identity_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "brand_key",
            sa.String(64),
            nullable=False,
            server_default="breero",
        ),
        sa.Column("issuer", sa.String(512), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column(
            "linked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "brand_key",
            "issuer",
            "subject",
            name="uq_identity_link_subject",
        ),
        sa.UniqueConstraint(
            "brand_key",
            "issuer",
            "user_id",
            name="uq_identity_link_user_issuer",
        ),
    )
    op.create_index(
        "ix_identity_links_user_id",
        "identity_links",
        ["user_id"],
    )
    op.create_index(
        "ix_identity_links_email",
        "identity_links",
        ["email"],
    )

    op.create_table(
        "access_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "brand_key",
            sa.String(64),
            nullable=False,
            server_default="breero",
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
            "user_id",
            "brand_key",
            name="uq_access_profile_user_brand",
        ),
    )
    op.create_index(
        "ix_access_profiles_user_id",
        "access_profiles",
        ["user_id"],
    )

    op.create_table(
        "access_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "brand_key",
            sa.String(64),
            nullable=False,
            server_default="breero",
        ),
        sa.Column("role_key", sa.String(64), nullable=False),
        sa.Column("department", sa.String(64), nullable=False),
        sa.Column(
            "tenant_scope",
            sa.String(32),
            nullable=False,
            server_default="brand",
        ),
        sa.Column(
            "vendor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vendors.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "is_primary",
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
        sa.CheckConstraint(
            "(tenant_scope = 'vendor' AND vendor_id IS NOT NULL) OR "
            "(tenant_scope <> 'vendor' AND vendor_id IS NULL)",
            name="ck_access_assignment_vendor_scope",
        ),
        sa.UniqueConstraint(
            "user_id",
            "brand_key",
            "role_key",
            "department",
            name="uq_access_assignment_role_department",
        ),
    )
    op.create_index(
        "ix_access_assignments_user_id",
        "access_assignments",
        ["user_id"],
    )
    op.create_index(
        "ix_access_assignments_vendor_id",
        "access_assignments",
        ["vendor_id"],
    )
    op.create_index(
        "ix_access_assignments_department",
        "access_assignments",
        ["department"],
    )

    op.create_table(
        "role_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("role_key", sa.String(64), nullable=False),
        sa.Column("permission", sa.String(128), nullable=False),
        sa.Column(
            "allow",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.UniqueConstraint(
            "role_key",
            "permission",
            name="uq_role_permission",
        ),
    )
    op.create_index(
        "ix_role_permissions_role_key",
        "role_permissions",
        ["role_key"],
    )

    op.create_table(
        "user_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "brand_key",
            sa.String(64),
            nullable=False,
            server_default="breero",
        ),
        sa.Column("permission", sa.String(128), nullable=False),
        sa.Column("allow", sa.Boolean(), nullable=False),
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
            "user_id",
            "brand_key",
            "permission",
            name="uq_user_permission",
        ),
    )
    op.create_index(
        "ix_user_permissions_user_id",
        "user_permissions",
        ["user_id"],
    )

    op.create_table(
        "account_invitation_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "token_hash",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_account_invitation_tokens_user_id",
        "account_invitation_tokens",
        ["user_id"],
    )
    op.create_index(
        "ix_account_invitation_tokens_token_hash",
        "account_invitation_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_account_invitation_tokens_expires_at",
        "account_invitation_tokens",
        ["expires_at"],
    )
    op.create_index(
        "ix_account_invitation_tokens_created_by",
        "account_invitation_tokens",
        ["created_by"],
    )


def downgrade():
    op.drop_table("account_invitation_tokens")
    op.drop_table("user_permissions")
    op.drop_table("role_permissions")
    op.drop_table("access_assignments")
    op.drop_table("access_profiles")
    op.drop_table("identity_links")
