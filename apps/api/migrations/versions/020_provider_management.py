"""provider services, skills, and service areas

Revision ID: 020_provider_management
Revises: 019_booking_lifecycle_states
"""

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

revision = "020_provider_management"
down_revision = "019_booking_lifecycle_states"
branch_labels = None
depends_on = None


def common() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def upgrade() -> None:
    op.create_table(
        "provider_services", *common(),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("services.id", ondelete="CASCADE"), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("approval_status", sa.String(24), nullable=False, server_default="PENDING"),
        sa.UniqueConstraint("provider_id", "service_id"),
    )
    op.create_index("ix_provider_services_lookup", "provider_services", ["provider_id", "service_id", "active", "approval_status"])
    op.create_table(
        "provider_skills", *common(),
        sa.Column("professional_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("services.id", ondelete="CASCADE"), nullable=False),
        sa.Column("skill", sa.String(120), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("approved", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("professional_id", "service_id", "skill"),
    )
    op.create_index("ix_provider_skills_lookup", "provider_skills", ["professional_id", "service_id", "active", "approved"])
    op.create_table(
        "provider_service_areas", *common(),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("professional_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workers.id", ondelete="CASCADE")),
        sa.Column("area_type", sa.String(24), nullable=False),
        sa.Column("service_zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("service_zones.id", ondelete="CASCADE")),
        sa.Column("postal_code", sa.String(5)), sa.Column("city", sa.String(120)),
        sa.Column("county", sa.String(120)), sa.Column("state", sa.String(3)),
        sa.Column("center", Geometry("POINT", srid=4326)), sa.Column("radius_meters", sa.Integer),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("approval_status", sa.String(24), nullable=False, server_default="PENDING"),
        sa.CheckConstraint("area_type IN ('ZIP','ZIP_GROUP','CITY','COUNTY','RADIUS','SERVICE_ZONE')", name="provider_area_type"),
    )
    op.create_index("ix_provider_service_areas_provider", "provider_service_areas", ["provider_id", "active", "approval_status"])
    op.create_index("ix_provider_service_areas_postal", "provider_service_areas", ["postal_code", "state"])
    op.create_index("ix_provider_service_areas_zone", "provider_service_areas", ["service_zone_id"])


def downgrade() -> None:
    op.drop_table("provider_service_areas")
    op.drop_table("provider_skills")
    op.drop_table("provider_services")
