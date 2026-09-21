"""bind capacity holds to service and address

Revision ID: 022_hold_scope
Revises: 021_client_address_fields
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "022_hold_scope"
down_revision = "021_client_address_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("booking_capacity_holds", sa.Column("service_id", postgresql.UUID(as_uuid=True)))
    op.add_column("booking_capacity_holds", sa.Column("address_id", postgresql.UUID(as_uuid=True)))
    op.create_foreign_key("fk_capacity_hold_service", "booking_capacity_holds", "services", ["service_id"], ["id"])
    op.create_foreign_key("fk_capacity_hold_address", "booking_capacity_holds", "addresses", ["address_id"], ["id"])
    op.create_index("ix_booking_capacity_holds_service_id", "booking_capacity_holds", ["service_id"])
    op.create_index("ix_booking_capacity_holds_address_id", "booking_capacity_holds", ["address_id"])
    # The table is new and empty in the protected release. Abort rather than invent scope if not.
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM booking_capacity_holds WHERE service_id IS NULL OR address_id IS NULL) "
        "THEN RAISE EXCEPTION 'capacity holds require explicit service/address backfill'; END IF; END $$"
    )
    op.alter_column("booking_capacity_holds", "service_id", nullable=False)
    op.alter_column("booking_capacity_holds", "address_id", nullable=False)


def downgrade() -> None:
    op.drop_index("ix_booking_capacity_holds_address_id", table_name="booking_capacity_holds")
    op.drop_index("ix_booking_capacity_holds_service_id", table_name="booking_capacity_holds")
    op.drop_constraint("fk_capacity_hold_address", "booking_capacity_holds", type_="foreignkey")
    op.drop_constraint("fk_capacity_hold_service", "booking_capacity_holds", type_="foreignkey")
    op.drop_column("booking_capacity_holds", "address_id")
    op.drop_column("booking_capacity_holds", "service_id")
