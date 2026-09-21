import uuid

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domains.common.models import TimestampMixin, UUIDPrimaryKeyMixin


class ProviderService(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "provider_services"
    __table_args__ = (UniqueConstraint("provider_id", "service_id"),)
    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vendors.id", ondelete="CASCADE"), index=True
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"), index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approval_status: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING")


class ProviderSkill(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "provider_skills"
    __table_args__ = (UniqueConstraint("professional_id", "service_id", "skill"),)
    professional_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workers.id", ondelete="CASCADE"), index=True
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"), index=True
    )
    skill: Mapped[str] = mapped_column(String(120), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ProviderServiceArea(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "provider_service_areas"
    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vendors.id", ondelete="CASCADE"), index=True
    )
    professional_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workers.id", ondelete="CASCADE"), index=True
    )
    area_type: Mapped[str] = mapped_column(String(24), nullable=False)
    service_zone_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("service_zones.id", ondelete="CASCADE"), index=True
    )
    postal_code: Mapped[str | None] = mapped_column(String(5), index=True)
    city: Mapped[str | None] = mapped_column(String(120), index=True)
    county: Mapped[str | None] = mapped_column(String(120), index=True)
    state: Mapped[str | None] = mapped_column(String(3), index=True)
    center: Mapped[object | None] = mapped_column(Geometry("POINT", srid=4326))
    radius_meters: Mapped[int | None] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approval_status: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING")
