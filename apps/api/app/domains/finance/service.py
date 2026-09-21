import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.domains.common.outbox import AuditLog, EventStatus, IntegrationEvent
from app.domains.jobs.models import Job, JobStatus
from app.integrations.payouts import (
    IntegrationNotConfigured,
    PayoutGateway,
    get_payout_gateway,
)

from .compensation import calculate_compensation
from .models import (
    AdjustmentType,
    CompensationSnapshot,
    EarningAdjustment,
    EarningStatus,
    PayoutBatch,
    PayoutStatus,
    VendorCompensationPlan,
    VendorEarning,
)
from .repository import FinanceRepository


class FinanceService:
    def __init__(self, session: AsyncSession, payout_gateway: PayoutGateway | None = None):
        self.session = session
        self.repo = FinanceRepository(session)
        self.payout_gateway = payout_gateway or get_payout_gateway()

    @staticmethod
    def require_payouts_enabled() -> None:
        # Check on every command, including retries on an existing service instance.
        # Recognition and corrective adjustments remain available to retain liabilities.
        if not settings.payout_enabled:
            raise HTTPException(503, "payouts_disabled")

    def audit(self, actor_id, action: str, resource_type: str, resource_id, metadata=None):
        self.session.add(
            AuditLog(
                actor_id=actor_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                metadata_json=metadata or {},
                created_at=datetime.now(UTC),
            )
        )

    async def create_compensation_plan(self, payload, actor_id) -> VendorCompensationPlan:
        if payload.method.value == "FIXED_MINOR" and payload.fixed_minor is None:
            raise HTTPException(422, "fixed_minor is required")
        if payload.method.value == "PERCENTAGE" and payload.percentage_bps is None:
            raise HTTPException(422, "percentage_bps is required")
        plan = VendorCompensationPlan(**payload.model_dump(), active=True)
        self.session.add(plan)
        await self.session.flush()
        self.audit(
            actor_id,
            "compensation_plan.change",
            "vendor_compensation_plan",
            plan.id,
            {"method": plan.method.value, "vendor_id": str(plan.vendor_id)},
        )
        await self.session.commit()
        await self.session.refresh(plan)
        return plan

    async def recognize_earning(
        self, job: Job, gross_minor: int, fee_minor: int = 0, currency: str = "USD"
    ) -> VendorEarning:
        """Create one earning and immutable compensation snapshot per completed job.

        fee_minor is retained for backwards compatibility but compensation always comes from a plan.
        """
        if job.status != JobStatus.COMPLETED or not job.vendor_id:
            raise HTTPException(409, "Only completed assigned jobs can create earnings")
        if gross_minor < 0 or fee_minor < 0:
            raise HTTPException(422, "Invalid earning amounts")
        existing = await self.repo.earning_for_job(job.id)
        if existing:
            return existing
        plan = await self.repo.active_plan(job.vendor_id)
        if not plan:
            raise HTTPException(409, "Vendor compensation plan is not configured")
        rate = await self.repo.service_rate(plan.id, job.service_id)
        try:
            calculation = calculate_compensation(plan, gross_minor, rate)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        committed_at = datetime.now(UTC)
        snapshot = CompensationSnapshot(
            plan_id=plan.id,
            vendor_id=job.vendor_id,
            service_id=job.service_id,
            method=plan.method,
            rule_json=calculation.rule,
            gross_minor=gross_minor,
            compensation_minor=calculation.amount_minor,
            currency=currency,
            hold_days=plan.hold_days,
            committed_at=committed_at,
        )
        self.session.add(snapshot)
        await self.session.flush()
        earning = VendorEarning(
            vendor_id=job.vendor_id,
            job_id=job.id,
            compensation_snapshot_id=snapshot.id,
            gross_minor=gross_minor,
            fee_minor=gross_minor - calculation.amount_minor,
            net_minor=calculation.amount_minor,
            adjustment_total_minor=0,
            currency=currency,
            status=EarningStatus.PENDING,
            available_at=committed_at + timedelta(days=plan.hold_days),
        )
        self.session.add(earning)
        # Transaction ownership belongs to the application command which recognizes
        # completion. Flushing here obtains IDs and checks constraints without making
        # the earning visible independently from the completed job and its events.
        await self.session.flush()
        return earning

    async def release_eligible(self) -> int:
        self.require_payouts_enabled()
        rows = list(
            (
                await self.session.scalars(
                    select(VendorEarning)
                    .where(
                        VendorEarning.status == EarningStatus.PENDING,
                        VendorEarning.available_at <= datetime.now(UTC),
                    )
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        for earning in rows:
            earning.status = EarningStatus.AVAILABLE
        await self.session.commit()
        return len(rows)

    async def adjust_earning(
        self,
        earning_id,
        amount_minor: int,
        adjustment_type: AdjustmentType,
        reason: str,
        idempotency_key: str,
        actor_id=None,
    ) -> EarningAdjustment:
        self.require_payouts_enabled()
        earning = await self.session.scalar(
            select(VendorEarning).where(VendorEarning.id == earning_id).with_for_update()
        )
        if not earning:
            raise HTTPException(404, "Earning not found")
        existing = await self.session.scalar(
            select(EarningAdjustment).where(
                EarningAdjustment.earning_id == earning_id,
                EarningAdjustment.idempotency_key == idempotency_key,
            )
        )
        if existing:
            return existing
        adjustment = EarningAdjustment(
            earning_id=earning_id,
            amount_minor=amount_minor,
            adjustment_type=adjustment_type,
            reason=reason,
            idempotency_key=idempotency_key,
            actor_id=actor_id,
        )
        self.session.add(adjustment)
        earning.adjustment_total_minor += amount_minor
        if earning.payable_minor <= 0:
            earning.status = EarningStatus.REVERSED
        elif adjustment_type == AdjustmentType.DISPUTE:
            earning.status = EarningStatus.HELD
        self.audit(
            actor_id,
            "earning.adjustment",
            "vendor_earning",
            earning.id,
            {
                "amount_minor": amount_minor,
                "type": adjustment_type.value,
                "reason": reason,
            },
        )
        await self.session.commit()
        await self.session.refresh(adjustment)
        return adjustment

    async def create_batch(self, currency: str, vendor_id=None, actor_id=None) -> PayoutBatch:
        self.require_payouts_enabled()
        earnings = await self.repo.available_earnings(currency, vendor_id, lock=True)
        if not earnings:
            raise HTTPException(409, "No available earnings")
        batch = PayoutBatch(
            reference=f"PAY-{datetime.now(UTC):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}",
            status=PayoutStatus.PENDING_APPROVAL,
            currency=currency,
            total_minor=sum(e.payable_minor for e in earnings),
            earning_count=len(earnings),
            reviewed_by=actor_id,
            reviewed_at=datetime.now(UTC) if actor_id else None,
        )
        self.session.add(batch)
        await self.session.flush()
        for earning in earnings:
            earning.status = EarningStatus.BATCHED
            earning.payout_batch_id = batch.id
        self.audit(actor_id, "payout.review", "payout_batch", batch.id)
        await self.session.commit()
        await self.session.refresh(batch)
        return batch

    async def approve_batch(self, batch_id: uuid.UUID, approver_id: uuid.UUID) -> PayoutBatch:
        self.require_payouts_enabled()
        batch = await self.repo.get_batch(batch_id, lock=True)
        if not batch:
            raise HTTPException(404, "Payout batch not found")
        if batch.status != PayoutStatus.PENDING_APPROVAL:
            raise HTTPException(409, "Batch is not awaiting approval")
        if batch.reviewed_by == approver_id:
            raise HTTPException(409, "Batch reviewer cannot approve the same payout")
        batch.status = PayoutStatus.APPROVED
        batch.approved_by = approver_id
        batch.approved_at = datetime.now(UTC)
        self.audit(approver_id, "payout.approve", "payout_batch", batch.id)
        await self.session.commit()
        await self.session.refresh(batch)
        return batch

    async def submit_batch(self, batch_id: uuid.UUID, actor_id: uuid.UUID) -> PayoutBatch:
        self.require_payouts_enabled()
        batch = await self.repo.get_batch(batch_id, lock=True)
        if not batch:
            raise HTTPException(404, "Payout batch not found")
        if batch.provider_transfer_id:
            return batch
        if batch.status != PayoutStatus.APPROVED:
            raise HTTPException(409, "Only approved batches can be submitted")
        if batch.approved_by == actor_id:
            raise HTTPException(409, "Batch approver cannot submit the same payout")
        key = batch.idempotency_key or f"payout-batch:{batch.id}"
        batch.idempotency_key = key
        # Persist the stable key before the external call; retries reuse it.
        await self.session.commit()
        try:
            result = await self.payout_gateway.create_transfer(
                amount_minor=batch.total_minor,
                currency=batch.currency,
                destination=f"batch:{batch.id}",
                idempotency_key=key,
            )
        except IntegrationNotConfigured as exc:
            batch.failure_reason = exc.code
            await self.session.commit()
            raise HTTPException(503, exc.code) from exc
        batch.provider_transfer_id = result.transfer_id
        batch.provider_reference = result.provider_reference
        batch.provider_status = result.status
        batch.submitted_at = datetime.now(UTC)
        batch.status = PayoutStatus.PROCESSING
        self.session.add(
            IntegrationEvent(
                aggregate_type="payout",
                aggregate_id=batch.id,
                event_type="payout.submitted",
                payload={
                    "id": str(batch.id),
                    "reference": batch.reference,
                    "total_minor": batch.total_minor,
                    "currency": batch.currency,
                    "provider_status": result.status,
                },
                status=EventStatus.PENDING,
                attempts=0,
                available_at=datetime.now(UTC),
            )
        )
        self.audit(
            actor_id,
            "payout.submit",
            "payout_batch",
            batch.id,
            {"provider_status": result.status},
        )
        await self.session.commit()
        await self.session.refresh(batch)
        return batch
