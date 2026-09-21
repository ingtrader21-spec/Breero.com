"""expand explicit booking lifecycle states

Revision ID: 019_booking_lifecycle_states
Revises: 018_booking_capacity_foundation
"""

from alembic import op

revision = "019_booking_lifecycle_states"
down_revision = "018_booking_capacity_foundation"
branch_labels = None
depends_on = None

VALUES = (
    "DRAFT", "PENDING_REVIEW", "ADDRESS_VALIDATED", "COVERAGE_CONFIRMED",
    "AVAILABILITY_FOUND", "CAPACITY_HELD", "AWAITING_ASSIGNMENT", "PROVIDER_ASSIGNED",
    "EN_ROUTE", "IN_PROGRESS", "COMPLETED", "NO_COVERAGE", "NO_CAPACITY", "QUOTE_REQUIRED",
    "PROVIDER_DECLINED", "REASSIGNMENT_REQUIRED", "RESCHEDULED",
)


def upgrade() -> None:
    for value in VALUES:
        op.execute(f"ALTER TYPE booking_status ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    # PostgreSQL enum values are retained intentionally for rollback safety.
    pass
