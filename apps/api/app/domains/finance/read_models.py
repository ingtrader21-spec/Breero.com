"""Read-only finance projections for admin and provider portals.

Nothing here calculates new liabilities or moves money: every amount is read from
persisted earnings, payout batches, payments and refunds.
"""

import enum
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.domains.payments.models import PaymentPurpose, PaymentStatus, RefundStatus

from .models import EarningStatus, PayoutStatus


class FinanceCapabilityState(enum.StrEnum):
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


class FinanceStatus(BaseModel):
    payouts_enabled: bool
    payments_enabled: bool
    capabilities: dict[str, FinanceCapabilityState]


class PayoutAction(enum.StrEnum):
    approve = "approve"
    submit = "submit"


class PayoutBatchSummary(BaseModel):
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


class PayoutBatchPage(BaseModel):
    items: list[PayoutBatchSummary]
    total: int
    page: int
    page_size: int


class PayoutBatchEarning(BaseModel):
    id: uuid.UUID
    vendor_id: uuid.UUID
    job_id: uuid.UUID
    net_minor: int
    adjustment_total_minor: int
    payable_minor: int
    currency: str
    status: EarningStatus


class PayoutVendorTotal(BaseModel):
    vendor_id: uuid.UUID
    earning_count: int
    total_minor: int


PayoutHistoryState = Literal["CREATED", "APPROVED", "SUBMITTED", "SUBMISSION_BLOCKED", "CURRENT"]


class PayoutHistoryEntry(BaseModel):
    state: PayoutHistoryState
    status: PayoutStatus | None = None
    occurred_at: datetime | None
    actor_id: uuid.UUID | None = None
    detail: str | None = None


class PayoutBatchDetail(PayoutBatchSummary):
    provider_reference: str | None
    earnings: list[PayoutBatchEarning]
    vendor_totals: list[PayoutVendorTotal]
    history: list[PayoutHistoryEntry]
    allowed_actions: list[PayoutAction]
    payouts_enabled: bool


class PayoutCandidates(BaseModel):
    currency: str
    vendor_id: uuid.UUID | None
    earning_count: int
    total_minor: int
    payouts_enabled: bool


class EarningStatusTotal(BaseModel):
    currency: str
    status: EarningStatus
    earning_count: int
    payable_minor: int


class PendingPayoutTotal(BaseModel):
    currency: str
    eligible_count: int
    eligible_minor: int
    pending_release_minor: int
    held_minor: int
    in_batch_minor: int
    paid_minor: int


class EarningsSummary(BaseModel):
    vendor_id: uuid.UUID | None
    by_status: list[EarningStatusTotal]
    pending_payouts: list[PendingPayoutTotal]
    payouts_enabled: bool


class FinanceExceptionKind(enum.StrEnum):
    EARNING_HELD = "EARNING_HELD"
    EARNING_REVERSED = "EARNING_REVERSED"
    PAYOUT_FAILED = "PAYOUT_FAILED"
    PAYOUT_SUBMISSION_BLOCKED = "PAYOUT_SUBMISSION_BLOCKED"
    PAYOUT_PROCESSING_STALE = "PAYOUT_PROCESSING_STALE"


class FinanceException(BaseModel):
    kind: FinanceExceptionKind
    resource_type: Literal["vendor_earning", "payout_batch"]
    resource_id: uuid.UUID
    status: str
    currency: str
    amount_minor: int
    vendor_id: uuid.UUID | None = None
    reference: str | None = None
    reason: str | None = None
    occurred_at: datetime | None


class FinanceExceptionList(BaseModel):
    items: list[FinanceException]
    total: int


class EarningRecord(BaseModel):
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


class EarningPage(BaseModel):
    items: list[EarningRecord]
    total: int
    page: int
    page_size: int


class ProviderFinanceSummary(BaseModel):
    vendor_id: uuid.UUID
    by_status: list[EarningStatusTotal]
    pending_payouts: list[PendingPayoutTotal]
    payouts_enabled: bool


class ProviderPayout(BaseModel):
    """A payout batch as seen by one vendor: only that vendor's share is exposed."""

    id: uuid.UUID
    reference: str
    status: PayoutStatus
    currency: str
    vendor_total_minor: int
    vendor_earning_count: int
    created_at: datetime
    approved_at: datetime | None
    submitted_at: datetime | None


class ProviderPayoutPage(BaseModel):
    items: list[ProviderPayout]
    total: int
    page: int
    page_size: int


class ProviderPayoutHistoryEntry(BaseModel):
    # Internal submission diagnostics (SUBMISSION_BLOCKED) are filtered out for providers.
    state: PayoutHistoryState
    status: PayoutStatus | None = None
    occurred_at: datetime | None


class ProviderPayoutDetail(ProviderPayout):
    earnings: list[EarningRecord]
    history: list[ProviderPayoutHistoryEntry]


class PaymentRecord(BaseModel):
    """Payment inventory row. Client secrets and raw metadata are never exposed."""

    id: uuid.UUID
    payment_purpose: PaymentPurpose
    booking_id: uuid.UUID | None
    quote_id: uuid.UUID | None
    lead_purchase_id: uuid.UUID | None
    provider: str
    provider_payment_id: str | None
    status: PaymentStatus
    amount_minor: int
    captured_amount_minor: int
    currency: str
    failure_code: str | None
    created_at: datetime
    updated_at: datetime


class PaymentPage(BaseModel):
    items: list[PaymentRecord]
    total: int
    page: int
    page_size: int


class RefundRecord(BaseModel):
    id: uuid.UUID
    payment_id: uuid.UUID
    amount_minor: int
    status: RefundStatus
    provider_refund_id: str | None
    reason: str | None
    created_by: uuid.UUID
    created_at: datetime


class RefundPage(BaseModel):
    items: list[RefundRecord]
    total: int
    page: int
    page_size: int
