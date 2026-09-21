"""tenant email domains, senders, credentials and queued messages

Revision ID: 032_tenant_email_provisioning
Revises: 031_provider_catalog
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "032_tenant_email_provisioning"
down_revision = "031_provider_catalog"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "email_domains",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_key", sa.String(64), nullable=False, server_default="breero"),
        sa.Column(
            "vendor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vendors.id", ondelete="CASCADE"),
        ),
        sa.Column("domain", sa.String(253), nullable=False, unique=True),
        sa.Column("verification_status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("dkim_selector", sa.String(63)),
        sa.Column("return_path_domain", sa.String(253)),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_email_domains_brand_key", "email_domains", ["brand_key"])
    op.create_index("ix_email_domains_vendor_id", "email_domains", ["vendor_id"])
    op.create_index("ix_email_domains_domain", "email_domains", ["domain"], unique=True)
    op.create_index("ix_email_domains_created_by", "email_domains", ["created_by"])

    op.create_table(
        "email_senders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_key", sa.String(64), nullable=False, server_default="breero"),
        sa.Column(
            "vendor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vendors.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "domain_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("email_domains.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("local_part", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("reply_to", sa.String(320)),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("domain_id", "local_part", name="uq_email_sender_address"),
    )
    op.create_index("ix_email_senders_brand_key", "email_senders", ["brand_key"])
    op.create_index("ix_email_senders_vendor_id", "email_senders", ["vendor_id"])
    op.create_index("ix_email_senders_domain_id", "email_senders", ["domain_id"])
    op.create_index("ix_email_senders_created_by", "email_senders", ["created_by"])

    op.create_table(
        "email_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_key", sa.String(64), nullable=False, server_default="breero"),
        sa.Column(
            "vendor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vendors.id", ondelete="CASCADE"),
        ),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("username", sa.String(320)),
        sa.Column("secret_ref", sa.String(255), nullable=False, unique=True),
        sa.Column("smtp_host", sa.String(253)),
        sa.Column("smtp_port", sa.Integer()),
        sa.Column("use_tls", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_email_credentials_brand_key", "email_credentials", ["brand_key"])
    op.create_index("ix_email_credentials_vendor_id", "email_credentials", ["vendor_id"])
    op.create_index("ix_email_credentials_created_by", "email_credentials", ["created_by"])

    op.create_table(
        "email_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_key", sa.String(64), nullable=False, server_default="breero"),
        sa.Column(
            "vendor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vendors.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "sender_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("email_senders.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "credential_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("email_credentials.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("to_email", sa.String(320), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("text_body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("idempotency_key", sa.String(255), nullable=False, unique=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("queued_at", sa.DateTime(timezone=True)),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("provider_message_id", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_email_messages_brand_key", "email_messages", ["brand_key"])
    op.create_index("ix_email_messages_vendor_id", "email_messages", ["vendor_id"])
    op.create_index("ix_email_messages_sender_id", "email_messages", ["sender_id"])
    op.create_index("ix_email_messages_credential_id", "email_messages", ["credential_id"])
    op.create_index("ix_email_messages_to_email", "email_messages", ["to_email"])
    op.create_index("ix_email_messages_status", "email_messages", ["status"])
    op.create_index("ix_email_messages_idempotency_key", "email_messages", ["idempotency_key"], unique=True)
    op.create_index("ix_email_messages_created_by", "email_messages", ["created_by"])


def downgrade():
    op.drop_table("email_messages")
    op.drop_table("email_credentials")
    op.drop_table("email_senders")
    op.drop_table("email_domains")
