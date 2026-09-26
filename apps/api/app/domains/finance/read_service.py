"""Read-only finance queries for admin and provider portals.

These queries never call a payment or payout provider and never mutate state, so
they stay available while payout commands are disabled. Provider-scoped methods
always take the vendor resolved from the authenticated account, never from input.
"""

import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.errors import DomainError
from app.domains.auth.models import User
from app.domains.payments.models import Payment, PaymentStatus, Refund, RefundStatus
from app.domains.workforce.models import Vendor

from .models import EarningStatus, PayoutBatch, PayoutStatus, VendorEarning
from .read_models import (
    EarningPage,
    EarningRecord,
    EarningsSummary,
    EarningStatusTotal,
    FinanceCapabilityState,
    FinanceException,
    FinanceExceptionKind,
    FinanceExceptionList,
    FinanceStatus,
    PaymentPage,
    PaymentRecord,
    PayoutAction,
    PayoutBatchDetail,
    PayoutBatchEarning,
    PayoutBatchPage,
    PayoutBatchSummary,
    PayoutCandidates,
    PayoutHistoryEntry,
    PayoutVendorTotal,
    PendingPayoutTotal,
    ProviderFinanceSummary,
    ProviderPayout,
    ProviderPayoutDetail,
    ProviderPayoutHistoryEntry,
    ProviderPayoutPage,
    RefundPage,
    RefundRecord,
)

PAYABLE = VendorEarning.net_minor + VendorEarning.adjustment_total_minor
STALE_PROCESSING_AFTER = timedelta(days=7)
EXCEPTION_LIMIT = 500


def finance_status() -> FinanceStatus:
    payouts = settings.payout_enabled
    payments = settings.payments_enabled and settings.stripe_enabled
    enabled, disabled = FinanceCapabilityState.ENABLED, FinanceCapabilityState.DISABLED
    return FinanceStatus(
        payouts_enabled=payouts,
        payments_enabled=payments,
        capabilities={
            "earnings_read": enabled,
            "payout_batches_read": enabled,
            "payments_read": enabled,
            "refunds_read": enabled,
            # Create/approve/submit stay behind the existing PAYOUT_ENABLED gate.
            "payout_commands": enabled if payouts else disabled,
            # No live banking adapter exists; submission fails closed even when enabled.
            "payout_transfer": FinanceCapabilityState.NOT_IMPLEMENTED,
            # Admin refund issuance and manual capture are not exposed by any
            # finance-owned API; customer payment flows keep their own gates.
            "refund_commands": FinanceCapabilityState.NOT_IMPLEMENTED,
            "payment_commands": FinanceCapabilityState.NOT_IMPLEMENTED,
        },
    )


def _earning_record(earning: VendorEarning) -> EarningRecord:
    return EarningRecord(
        id=earning.id,
        vendor_id=earning.vendor_id,
        job_id=earning.job_id,
        gross_minor=earning.gross_minor,
        fee_minor=earning.fee_minor,
        net_minor=earning.net_minor,
        adjustment_total_minor=earning.adjustment_total_minor,
        payable_minor=earning.payable_minor,
        currency=earning.currency,
        status=earning.status,
        available_at=earning.available_at,
        payout_batch_id=earning.payout_batch_id,
        created_at=earning.created_at,
    )


def allowed_payout_actions(
    batch: PayoutBatch, viewer_id: uuid.UUID | None = None
) -> list[PayoutAction]:
    if not settings.payout_enabled:
        return []
    if batch.status == PayoutStatus.PENDING_APPROVAL:
        # Four-eyes control: the reviewer who created the batch cannot approve it.
        if viewer_id is not None and batch.reviewed_by == viewer_id:
            return []
        return [PayoutAction.approve]
    if batch.status == PayoutStatus.APPROVED and not batch.provider_transfer_id:
        return [PayoutAction.submit]
    return []


def payout_history(batch: PayoutBatch) -> list[PayoutHistoryEntry]:
    history = [
        PayoutHistoryEntry(
            state="CREATED",
            status=PayoutStatus.PENDING_APPROVAL,
            occurred_at=batch.reviewed_at or batch.created_at,
            actor_id=batch.reviewed_by,
        )
    ]
    if batch.approved_at:
        history.append(
            PayoutHistoryEntry(
                state="APPROVED",
                status=PayoutStatus.APPROVED,
                occurred_at=batch.approved_at,
                actor_id=batch.approved_by,
            )
        )
    if batch.submitted_at:
        history.append(
            PayoutHistoryEntry(
                state="SUBMITTED",
                status=PayoutStatus.PROCESSING,
                occurred_at=batch.submitted_at,
                detail=batch.provider_status,
            )
        )
    elif batch.failure_reason and batch.status == PayoutStatus.APPROVED:
        history.append(
            PayoutHistoryEntry(
                state="SUBMISSION_BLOCKED",
                status=batch.status,
                occurred_at=None,
                detail=batch.failure_reason,
            )
        )
    history.append(
        PayoutHistoryEntry(
            state="CURRENT",
            status=batch.status,
            occurred_at=None,
            detail=batch.failure_reason if batch.status == PayoutStatus.FAILED else None,
        )
    )
    return history


class FinanceReadService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ----- earnings -------------------------------------------------------

    async def earnings_page(
        self,
        *,
        vendor_id: uuid.UUID | None,
        status: EarningStatus | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> EarningPage:
        filters = []
        if vendor_id is not None:
            filters.append(VendorEarning.vendor_id == vendor_id)
        if status is not None:
            filters.append(VendorEarning.status == status)
        total = await self.session.scalar(
            select(func.count()).select_from(VendorEarning).where(*filters)
        )
        rows = (
            await self.session.scalars(
                select(VendorEarning)
                .where(*filters)
                .order_by(VendorEarning.created_at.desc(), VendorEarning.id)
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
        ).all()
        return EarningPage(
            items=[_earning_record(row) for row in rows],
            total=int(total or 0),
            page=page,
            page_size=page_size,
        )

    async def earning_totals(
        self, vendor_id: uuid.UUID | None
    ) -> tuple[list[EarningStatusTotal], list[PendingPayoutTotal]]:
        filters = [VendorEarning.vendor_id == vendor_id] if vendor_id is not None else []
        rows = (
            await self.session.execute(
                select(
                    VendorEarning.currency,
                    VendorEarning.status,
                    func.count(VendorEarning.id),
                    func.coalesce(func.sum(PAYABLE), 0),
                )
                .where(*filters)
                .group_by(VendorEarning.currency, VendorEarning.status)
                .order_by(VendorEarning.currency, VendorEarning.status)
            )
        ).all()
        eligible_rows = (
            await self.session.execute(
                select(
                    VendorEarning.currency,
                    func.count(VendorEarning.id),
                    func.coalesce(func.sum(PAYABLE), 0),
                )
                .where(
                    *filters,
                    VendorEarning.status == EarningStatus.AVAILABLE,
                    VendorEarning.available_at <= datetime.now(UTC),
                )
                .group_by(VendorEarning.currency)
            )
        ).all()
        by_status = [
            EarningStatusTotal(
                currency=currency,
                status=status,
                earning_count=int(count),
                payable_minor=int(amount),
            )
            for currency, status, count, amount in rows
        ]
        buckets: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for item in by_status:
            bucket = buckets[item.currency]
            if item.status == EarningStatus.PENDING:
                bucket["pending_release_minor"] += item.payable_minor
            elif item.status == EarningStatus.HELD:
                bucket["held_minor"] += item.payable_minor
            elif item.status in {EarningStatus.BATCHED, EarningStatus.APPROVED}:
                bucket["in_batch_minor"] += item.payable_minor
            elif item.status == EarningStatus.PAID:
                bucket["paid_minor"] += item.payable_minor
        for currency, count, amount in eligible_rows:
            buckets[currency]["eligible_count"] += int(count)
            buckets[currency]["eligible_minor"] += int(amount)
        pending = [
            PendingPayoutTotal(
                currency=currency,
                eligible_count=values["eligible_count"],
                eligible_minor=values["eligible_minor"],
                pending_release_minor=values["pending_release_minor"],
                held_minor=values["held_minor"],
                in_batch_minor=values["in_batch_minor"],
                paid_minor=values["paid_minor"],
            )
            for currency, values in sorted(buckets.items())
        ]
        return by_status, pending

    async def earnings_summary(self, vendor_id: uuid.UUID | None = None) -> EarningsSummary:
        by_status, pending = await self.earning_totals(vendor_id)
        return EarningsSummary(
            vendor_id=vendor_id,
            by_status=by_status,
            pending_payouts=pending,
            payouts_enabled=settings.payout_enabled,
        )

    # ----- payout batches -------------------------------------------------

    async def payout_batches(
        self,
        *,
        status: PayoutStatus | None = None,
        currency: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> PayoutBatchPage:
        filters = []
        if status is not None:
            filters.append(PayoutBatch.status == status)
        if currency is not None:
            filters.append(PayoutBatch.currency == currency)
        total = await self.session.scalar(
            select(func.count()).select_from(PayoutBatch).where(*filters)
        )
        rows = (
            await self.session.scalars(
                select(PayoutBatch)
                .where(*filters)
                .order_by(PayoutBatch.created_at.desc(), PayoutBatch.id)
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
        ).all()
        return PayoutBatchPage(
            items=[PayoutBatchSummary.model_validate(row) for row in rows],
            total=int(total or 0),
            page=page,
            page_size=page_size,
        )

    async def _batch(self, batch_id: uuid.UUID) -> PayoutBatch:
        batch = await self.session.scalar(select(PayoutBatch).where(PayoutBatch.id == batch_id))
        if batch is None:
            raise DomainError("PAYOUT_BATCH_NOT_FOUND", "Payout batch not found.", 404)
        return batch

    async def payout_batch(
        self, batch_id: uuid.UUID, viewer_id: uuid.UUID | None = None
    ) -> PayoutBatchDetail:
        batch = await self._batch(batch_id)
        earnings = list(
            (
                await self.session.scalars(
                    select(VendorEarning)
                    .where(VendorEarning.payout_batch_id == batch.id)
                    .order_by(VendorEarning.vendor_id, VendorEarning.created_at)
                )
            ).all()
        )
        totals: dict[uuid.UUID, list[int]] = defaultdict(lambda: [0, 0])
        for earning in earnings:
            totals[earning.vendor_id][0] += 1
            totals[earning.vendor_id][1] += earning.payable_minor
        summary = PayoutBatchSummary.model_validate(batch)
        return PayoutBatchDetail(
            **summary.model_dump(),
            provider_reference=batch.provider_reference,
            earnings=[
                PayoutBatchEarning(
                    id=earning.id,
                    vendor_id=earning.vendor_id,
                    job_id=earning.job_id,
                    net_minor=earning.net_minor,
                    adjustment_total_minor=earning.adjustment_total_minor,
                    payable_minor=earning.payable_minor,
                    currency=earning.currency,
                    status=earning.status,
                )
                for earning in earnings
            ],
            vendor_totals=[
                PayoutVendorTotal(vendor_id=vendor_id, earning_count=count, total_minor=amount)
                for vendor_id, (count, amount) in totals.items()
            ],
            history=payout_history(batch),
            allowed_actions=allowed_payout_actions(batch, viewer_id),
            payouts_enabled=settings.payout_enabled,
        )

    async def payout_history(self, batch_id: uuid.UUID) -> list[PayoutHistoryEntry]:
        return payout_history(await self._batch(batch_id))

    async def payout_candidates(
        self, currency: str, vendor_id: uuid.UUID | None = None
    ) -> PayoutCandidates:
        filters = [
            VendorEarning.status == EarningStatus.AVAILABLE,
            VendorEarning.available_at <= datetime.now(UTC),
            VendorEarning.currency == currency,
        ]
        if vendor_id is not None:
            filters.append(VendorEarning.vendor_id == vendor_id)
        count, amount = (
            await self.session.execute(
                select(func.count(VendorEarning.id), func.coalesce(func.sum(PAYABLE), 0)).where(
                    *filters
                )
            )
        ).one()
        return PayoutCandidates(
            currency=currency,
            vendor_id=vendor_id,
            earning_count=int(count),
            total_minor=int(amount),
            payouts_enabled=settings.payout_enabled,
        )

    async def exceptions(self) -> FinanceExceptionList:
        items: list[FinanceException] = []
        earnings = (
            await self.session.scalars(
                select(VendorEarning)
                .where(VendorEarning.status.in_([EarningStatus.HELD, EarningStatus.REVERSED]))
                .order_by(VendorEarning.created_at.desc())
                .limit(EXCEPTION_LIMIT)
            )
        ).all()
        for earning in earnings:
            items.append(
                FinanceException(
                    kind=(
                        FinanceExceptionKind.EARNING_HELD
                        if earning.status == EarningStatus.HELD
                        else FinanceExceptionKind.EARNING_REVERSED
                    ),
                    resource_type="vendor_earning",
                    resource_id=earning.id,
                    status=earning.status.value,
                    currency=earning.currency,
                    amount_minor=earning.payable_minor,
                    vendor_id=earning.vendor_id,
                    occurred_at=earning.created_at,
                )
            )
        stale_before = datetime.now(UTC) - STALE_PROCESSING_AFTER
        batches = (
            await self.session.scalars(
                select(PayoutBatch)
                .where(
                    (PayoutBatch.status == PayoutStatus.FAILED)
                    | (
                        (PayoutBatch.status == PayoutStatus.APPROVED)
                        & PayoutBatch.failure_reason.is_not(None)
                    )
                    | (
                        (PayoutBatch.status == PayoutStatus.PROCESSING)
                        & (PayoutBatch.submitted_at < stale_before)
                    )
                )
                .order_by(PayoutBatch.created_at.desc())
                .limit(EXCEPTION_LIMIT)
            )
        ).all()
        for batch in batches:
            if batch.status == PayoutStatus.FAILED:
                kind = FinanceExceptionKind.PAYOUT_FAILED
            elif batch.status == PayoutStatus.APPROVED:
                kind = FinanceExceptionKind.PAYOUT_SUBMISSION_BLOCKED
            else:
                kind = FinanceExceptionKind.PAYOUT_PROCESSING_STALE
            items.append(
                FinanceException(
                    kind=kind,
                    resource_type="payout_batch",
                    resource_id=batch.id,
                    status=batch.status.value,
                    currency=batch.currency,
                    amount_minor=batch.total_minor,
                    reference=batch.reference,
                    reason=batch.failure_reason,
                    occurred_at=batch.submitted_at or batch.approved_at or batch.created_at,
                )
            )
        return FinanceExceptionList(items=items, total=len(items))

    # ----- payment / refund inventory (read-only) -------------------------

    async def payments(
        self,
        *,
        status: PaymentStatus | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> PaymentPage:
        filters = [Payment.status == status] if status is not None else []
        total = await self.session.scalar(
            select(func.count()).select_from(Payment).where(*filters)
        )
        rows = (
            await self.session.scalars(
                select(Payment)
                .where(*filters)
                .order_by(Payment.created_at.desc(), Payment.id)
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
        ).all()
        return PaymentPage(
            items=[
                PaymentRecord(
                    id=row.id,
                    payment_purpose=row.payment_purpose,
                    booking_id=row.booking_id,
                    quote_id=row.quote_id,
                    lead_purchase_id=row.lead_purchase_id,
                    provider=row.provider,
                    provider_payment_id=row.provider_payment_id,
                    status=row.status,
                    amount_minor=row.amount_minor,
                    captured_amount_minor=row.captured_amount_minor,
                    currency=row.currency,
                    failure_code=row.failure_code,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
                for row in rows
            ],
            total=int(total or 0),
            page=page,
            page_size=page_size,
        )

    async def refunds(
        self,
        *,
        status: RefundStatus | None = None,
        payment_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> RefundPage:
        filters = []
        if status is not None:
            filters.append(Refund.status == status)
        if payment_id is not None:
            filters.append(Refund.payment_id == payment_id)
        total = await self.session.scalar(
            select(func.count()).select_from(Refund).where(*filters)
        )
        rows = (
            await self.session.scalars(
                select(Refund)
                .where(*filters)
                .order_by(Refund.created_at.desc(), Refund.id)
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
        ).all()
        return RefundPage(
            items=[
                RefundRecord(
                    id=row.id,
                    payment_id=row.payment_id,
                    amount_minor=row.amount_minor,
                    status=row.status,
                    provider_refund_id=row.provider_refund_id,
                    reason=row.reason,
                    created_by=row.created_by,
                    created_at=row.created_at,
                )
                for row in rows
            ],
            total=int(total or 0),
            page=page,
            page_size=page_size,
        )


class ProviderFinanceService:
    """Finance reads for the authenticated provider organization only."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.reads = FinanceReadService(session)

    async def vendor_id_for(self, user: User) -> uuid.UUID:
        vendor_id = await self.session.scalar(
            select(Vendor.id).where(Vendor.owner_user_id == user.id)
        )
        if vendor_id is None:
            raise DomainError(
                "PROVIDER_ACCOUNT_REQUIRED",
                "Account does not administer a provider organization.",
                403,
            )
        return vendor_id

    async def summary(self, user: User) -> ProviderFinanceSummary:
        vendor_id = await self.vendor_id_for(user)
        by_status, pending = await self.reads.earning_totals(vendor_id)
        return ProviderFinanceSummary(
            vendor_id=vendor_id,
            by_status=by_status,
            pending_payouts=pending,
            payouts_enabled=settings.payout_enabled,
        )

    async def earnings(
        self,
        user: User,
        *,
        status: EarningStatus | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> EarningPage:
        vendor_id = await self.vendor_id_for(user)
        return await self.reads.earnings_page(
            vendor_id=vendor_id, status=status, page=page, page_size=page_size
        )

    async def payouts(
        self, user: User, *, page: int = 1, page_size: int = 25
    ) -> ProviderPayoutPage:
        vendor_id = await self.vendor_id_for(user)
        total = await self.session.scalar(
            select(func.count(func.distinct(VendorEarning.payout_batch_id))).where(
                VendorEarning.vendor_id == vendor_id,
                VendorEarning.payout_batch_id.is_not(None),
            )
        )
        rows = (
            await self.session.execute(
                select(
                    PayoutBatch,
                    func.count(VendorEarning.id),
                    func.coalesce(func.sum(PAYABLE), 0),
                )
                .join(VendorEarning, VendorEarning.payout_batch_id == PayoutBatch.id)
                .where(VendorEarning.vendor_id == vendor_id)
                .group_by(PayoutBatch.id)
                .order_by(PayoutBatch.created_at.desc(), PayoutBatch.id)
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
        ).all()
        return ProviderPayoutPage(
            items=[self._payout(batch, int(count), int(amount)) for batch, count, amount in rows],
            total=int(total or 0),
            page=page,
            page_size=page_size,
        )

    async def payout(self, user: User, batch_id: uuid.UUID) -> ProviderPayoutDetail:
        vendor_id = await self.vendor_id_for(user)
        earnings = list(
            (
                await self.session.scalars(
                    select(VendorEarning)
                    .where(
                        VendorEarning.payout_batch_id == batch_id,
                        VendorEarning.vendor_id == vendor_id,
                    )
                    .order_by(VendorEarning.created_at)
                )
            ).all()
        )
        batch = (
            await self.session.scalar(select(PayoutBatch).where(PayoutBatch.id == batch_id))
            if earnings
            else None
        )
        if batch is None:
            # Batches without this vendor's earnings are indistinguishable from missing ones.
            raise DomainError("PAYOUT_NOT_FOUND", "Payout not found.", 404)
        summary = self._payout(
            batch, len(earnings), sum(earning.payable_minor for earning in earnings)
        )
        return ProviderPayoutDetail(
            **summary.model_dump(),
            earnings=[_earning_record(earning) for earning in earnings],
            history=[
                ProviderPayoutHistoryEntry(
                    state=entry.state,
                    status=entry.status,
                    occurred_at=entry.occurred_at,
                )
                for entry in payout_history(batch)
                if entry.state != "SUBMISSION_BLOCKED"
            ],
        )

    @staticmethod
    def _payout(batch: PayoutBatch, count: int, amount: int) -> ProviderPayout:
        return ProviderPayout(
            id=batch.id,
            reference=batch.reference,
            status=batch.status,
            currency=batch.currency,
            vendor_total_minor=amount,
            vendor_earning_count=count,
            created_at=batch.created_at,
            approved_at=batch.approved_at,
            submitted_at=batch.submitted_at,
        )
