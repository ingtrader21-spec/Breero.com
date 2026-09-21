"""account setup state and booking request notes

Revision ID: 023_account_setup_notes
Revises: 022_hold_scope
"""

import sqlalchemy as sa
from alembic import op

revision = "023_account_setup_notes"
down_revision = "022_hold_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "password_set_required", sa.Boolean, nullable=False, server_default=sa.false()
        ),
    )
    op.add_column("bookings", sa.Column("request_note", sa.Text))


def downgrade() -> None:
    op.drop_column("bookings", "request_note")
    op.drop_column("users", "password_set_required")
