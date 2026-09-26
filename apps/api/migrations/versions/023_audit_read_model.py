"""add audit read-model context columns and bounded-search indexes

Revision ID: 023_audit_read_model
Revises: 022_provider_services_skills

Additive only. Existing rows keep NULL request/correlation/source/vendor context
and are classified ``success`` because every pre-existing emitter recorded only
committed, successful mutations. No audit row is updated, moved, or deleted.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "023_audit_read_model"
down_revision = "022_provider_services_skills"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audit_logs",
        sa.Column("result", sa.String(16), nullable=False, server_default="success"),
    )
    op.add_column("audit_logs", sa.Column("request_id", sa.String(128), nullable=True))
    op.add_column("audit_logs", sa.Column("correlation_id", sa.String(128), nullable=True))
    op.add_column("audit_logs", sa.Column("source_ip_hash", sa.String(64), nullable=True))
    op.add_column(
        "audit_logs",
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_audit_logs_result",
        "audit_logs",
        "result IN ('success', 'denied', 'failure')",
    )
    # Keyset pagination order for the default (newest first) listing.
    op.create_index(
        "ix_audit_logs_created_at_id",
        "audit_logs",
        [sa.text("created_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "ix_audit_logs_actor_created",
        "audit_logs",
        ["actor_id", sa.text("created_at DESC")],
    )
    # varchar_pattern_ops serves both exact action and "payout.%" prefix filters.
    op.create_index(
        "ix_audit_logs_action_created",
        "audit_logs",
        ["action", "created_at"],
        postgresql_ops={"action": "varchar_pattern_ops"},
    )
    op.create_index(
        "ix_audit_logs_resource_created",
        "audit_logs",
        ["resource_type", "resource_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_audit_logs_correlation_created",
        "audit_logs",
        ["correlation_id", "created_at"],
        postgresql_where=sa.text("correlation_id IS NOT NULL"),
    )
    op.create_index(
        "ix_audit_logs_result_created",
        "audit_logs",
        ["result", sa.text("created_at DESC")],
        postgresql_where=sa.text("result <> 'success'"),
    )
    op.create_index(
        "ix_audit_logs_vendor_created",
        "audit_logs",
        ["vendor_id", sa.text("created_at DESC")],
        postgresql_where=sa.text("vendor_id IS NOT NULL"),
    )


def downgrade() -> None:
    for name in (
        "ix_audit_logs_vendor_created",
        "ix_audit_logs_result_created",
        "ix_audit_logs_correlation_created",
        "ix_audit_logs_resource_created",
        "ix_audit_logs_action_created",
        "ix_audit_logs_actor_created",
        "ix_audit_logs_created_at_id",
    ):
        op.drop_index(name, table_name="audit_logs")
    op.drop_constraint("ck_audit_logs_result", "audit_logs", type_="check")
    op.drop_column("audit_logs", "vendor_id")
    op.drop_column("audit_logs", "source_ip_hash")
    op.drop_column("audit_logs", "correlation_id")
    op.drop_column("audit_logs", "request_id")
    op.drop_column("audit_logs", "result")
