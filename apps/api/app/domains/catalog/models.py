import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class QuestionType(enum.StrEnum):
    text = "text"
    textarea = "textarea"
    number = "number"
    boolean = "boolean"
    single_choice = "single_choice"
    multi_choice = "multi_choice"


class Service(Base):
    __tablename__ = "services"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="home-services")
    base_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    pricing_model: Mapped[str] = mapped_column(String(32), nullable=False, default="quote_required")
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_approval_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    before_buffer_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    after_buffer_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    emergency_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sunday_emergency_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    quote_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_bookable: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    questions: Mapped[list["ServiceQuestion"]] = relationship(
        back_populates="service",
        cascade="all, delete-orphan",
        order_by="ServiceQuestion.sort_order",
    )


class ServiceQuestion(Base):
    __tablename__ = "service_questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(100))
    label: Mapped[str] = mapped_column(String(240))
    help_text: Mapped[str | None] = mapped_column(Text)
    question_type: Mapped[QuestionType] = mapped_column(
        Enum(QuestionType, name="question_type", native_enum=True)
    )
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    options: Mapped[list[dict] | None] = mapped_column(JSONB)
    validation: Mapped[dict | None] = mapped_column(JSONB)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    service: Mapped[Service] = relationship(back_populates="questions")
