"""add hashed phone verification challenges

Revision ID: 025_phone_verification
Revises: 024_admin_controls
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "025_phone_verification"
down_revision = "024_admin_controls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "phone_verification_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_phone_verification_tokens_user_id", "phone_verification_tokens", ["user_id"]
    )
    op.create_index(
        "ix_phone_verification_tokens_token_hash",
        "phone_verification_tokens",
        ["token_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("phone_verification_tokens")
