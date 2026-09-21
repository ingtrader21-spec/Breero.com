"""client address labels and defaults

Revision ID: 021_client_address_fields
Revises: 020_provider_management
"""

import sqlalchemy as sa
from alembic import op

revision = "021_client_address_fields"
down_revision = "020_provider_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("addresses", sa.Column("label", sa.String(40), nullable=False, server_default="Home"))
    op.add_column("addresses", sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.false()))
    op.create_index("ix_addresses_customer_default", "addresses", ["customer_id", "is_default"])


def downgrade() -> None:
    op.drop_index("ix_addresses_customer_default", table_name="addresses")
    op.drop_column("addresses", "is_default")
    op.drop_column("addresses", "label")
