import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import AdjustmentType, CompensationMethod, EarningStatus, PayoutStatus


class FinanceVendorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    legal_name: str
    display_name: str
    status: str


class CompensationPlanCreate(BaseModel):
    vendor_id: uuid.UUID
    name: str = Field(min_length=1, max_length=160)
    method: CompensationMethod
    fixed_minor: int | None = Field(default=None, ge=0)
    percentage_bps: int | None = Field(default=None, ge=0, le=10_000)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    hold_days: int = Field(default=7, ge=0, le=365)
    effective_from: datetime


class CompensationPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    vendor_id: uuid.UUID
    name: str
    method: CompensationMethod
    fixed_minor: int | None
    percentage_bps: int | None
    currency: str
    hold_days: int
    active: bool
    effective_from: datetime
    effective_to: datetime | None
    created_at: datetime
    updated_at: datetime


class CompensationPlanList(BaseModel):
    items: list[CompensationPlanRead]
    total: int


class EarningAdjustmentCreate(BaseModel):
    amount_minor: int
    adjustment_type: AdjustmentType
    reason: str = Field(min_length=1, max_length=1000)
    idempotency_key: str = Field(min_length=1, max_length=128)


class EarningRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    vendor_id: uuid.UUID
    job_id: uuid.UUID
    gross_minor: int
    fee_minor: int
    net_minor: int
    adjustment_total_minor: int
    payable_minor: int
    currency: str
    status: EarningStatus
    available_at: datetime
    payout_batch_id: uuid.UUID | None
    created_at: datetime


class PayoutBatchCreate(BaseModel):
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    vendor_id: uuid.UUID | None = None


class PayoutBatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    reference: str
    status: PayoutStatus
    currency: str
    total_minor: int
    earning_count: int
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    submitted_at: datetime | None
    provider_status: str | None
    failure_reason: str | None
    created_at: datetime


class PayoutBatchList(BaseModel):
    items: list[PayoutBatchRead]
    total: int


class PayoutFailure(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
