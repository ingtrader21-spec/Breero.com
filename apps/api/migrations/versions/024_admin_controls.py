"""persist protected feature flags and service-local operating hours

Revision ID: 024_admin_controls
Revises: 023_account_setup_notes
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "024_admin_controls"
down_revision = "023_account_setup_notes"
branch_labels = None
depends_on = None

FLAGS = (
    "AUTO_ASSIGN_PROVIDER", "AUTO_CONFIRM_BOOKING", "PAYMENTS_ENABLED",
    "LIVE_PROVIDER_DISPATCH", "LIVE_EMAIL_DELIVERY", "LIVE_SMS_DELIVERY",
    "LIVE_CALLBACKS", "ODOO_DELIVERY_ENABLED", "ODOO_WRITE_ENABLED",
)


def upgrade() -> None:
    op.create_table(
        "feature_flags",
        sa.Column("key", sa.String(120), primary_key=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("description", sa.String(500), nullable=False, server_default=""),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    table = sa.table("feature_flags", sa.column("key", sa.String), sa.column("enabled", sa.Boolean), sa.column("description", sa.String))
    op.bulk_insert(table, [{"key": key, "enabled": False, "description": "Protected production safety flag"} for key in FLAGS])
    op.create_table(
        "operating_hours",
        sa.Column("day_of_week", sa.Integer, primary_key=True),
        sa.Column("start_local_time", sa.Time, nullable=False),
        sa.Column("end_local_time", sa.Time, nullable=False),
        sa.Column("emergency_only", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("day_of_week BETWEEN 0 AND 6", name="operating_hours_day"),
        sa.CheckConstraint("end_local_time > start_local_time", name="operating_hours_order"),
    )
    hours = sa.table("operating_hours", sa.column("day_of_week", sa.Integer), sa.column("start_local_time", sa.Time), sa.column("end_local_time", sa.Time), sa.column("emergency_only", sa.Boolean), sa.column("active", sa.Boolean))
    op.bulk_insert(hours, [{"day_of_week": day, "start_local_time": "07:00:00", "end_local_time": "19:00:00", "emergency_only": day == 6, "active": True} for day in range(7)])


def downgrade() -> None:
    op.drop_table("operating_hours")
    op.drop_table("feature_flags")
