"""add immutable Keycloak identity linkage

Revision ID: 026_keycloak_identity_link
Revises: 025_phone_verification
"""

import sqlalchemy as sa
from alembic import op

revision = "026_keycloak_identity_link"
down_revision = "025_phone_verification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("keycloak_subject", sa.String(255)))
    op.add_column("users", sa.Column("keycloak_issuer", sa.String(512)))
    op.add_column("users", sa.Column("keycloak_username", sa.String(320)))
    op.add_column("users", sa.Column("keycloak_linked_at", sa.DateTime(timezone=True)))
    op.create_index("ix_users_keycloak_subject", "users", ["keycloak_subject"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_keycloak_subject", table_name="users")
    op.drop_column("users", "keycloak_linked_at")
    op.drop_column("users", "keycloak_username")
    op.drop_column("users", "keycloak_issuer")
    op.drop_column("users", "keycloak_subject")
