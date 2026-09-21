import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    EarningStatus,
    PayoutBatch,
    PayoutStatus,
    VendorCompensationPlan,
    VendorEarning,
    VendorServiceCompensation,
)


class FinanceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_earnings(
        self,
        vendor_id: uuid.UUID | None = None,
        status: EarningStatus | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[VendorEarning]:
        query = (
            select(VendorEarning)
            .order_by(VendorEarning.created_at.desc(), VendorEarning.id)
            .limit(min(limit, 500))
            .offset(offset)
        )
        if vendor_id:
            query = query.where(VendorEarning.vendor_id == vendor_id)
        if status:
            query = query.where(VendorEarning.status == status)
        return list((await self.session.scalars(query)).all())

    async def count_earnings(
        self,
        vendor_id: uuid.UUID | None = None,
        status: EarningStatus | None = None,
    ) -> int:
        query = select(func.count()).select_from(VendorEarning)
        if vendor_id:
            query = query.where(VendorEarning.vendor_id == vendor_id)
        if status:
            query = query.where(VendorEarning.status == status)
        return int(await self.session.scalar(query) or 0)

    async def list_compensation_plans(
        self,
        vendor_id: uuid.UUID | None = None,
        active: bool | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[VendorCompensationPlan]:
        query = (
            select(VendorCompensationPlan)
            .order_by(
                VendorCompensationPlan.effective_from.desc(),
                VendorCompensationPlan.id,
            )
            .limit(min(limit, 500))
            .offset(offset)
        )
        if vendor_id:
            query = query.where(VendorCompensationPlan.vendor_id == vendor_id)
        if active is not None:
            query = query.where(VendorCompensationPlan.active.is_(active))
        return list((await self.session.scalars(query)).all())

    async def count_compensation_plans(
        self,
        vendor_id: uuid.UUID | None = None,
        active: bool | None = None,
    ) -> int:
        query = select(func.count()).select_from(VendorCompensationPlan)
        if vendor_id:
            query = query.where(VendorCompensationPlan.vendor_id == vendor_id)
        if active is not None:
            query = query.where(VendorCompensationPlan.active.is_(active))
        return int(await self.session.scalar(query) or 0)

    async def list_payout_batches(
        self,
        status: PayoutStatus | None = None,
        vendor_id: uuid.UUID | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[PayoutBatch]:
        query = select(PayoutBatch)
        if vendor_id:
            query = (
                query.join(
                    VendorEarning,
                    VendorEarning.payout_batch_id == PayoutBatch.id,
                )
                .where(VendorEarning.vendor_id == vendor_id)
                .distinct()
            )
        if status:
            query = query.where(PayoutBatch.status == status)
        query = (
            query.order_by(PayoutBatch.created_at.desc(), PayoutBatch.id)
            .limit(min(limit, 500))
            .offset(offset)
        )
        return list((await self.session.scalars(query)).all())

    async def count_payout_batches(
        self,
        status: PayoutStatus | None = None,
        vendor_id: uuid.UUID | None = None,
    ) -> int:
        if vendor_id:
            query = (
                select(func.count(func.distinct(PayoutBatch.id)))
                .select_from(PayoutBatch)
                .join(
                    VendorEarning,
                    VendorEarning.payout_batch_id == PayoutBatch.id,
                )
                .where(VendorEarning.vendor_id == vendor_id)
            )
        else:
            query = select(func.count()).select_from(PayoutBatch)
        if status:
            query = query.where(PayoutBatch.status == status)
        return int(await self.session.scalar(query) or 0)

    async def earning_for_job(self, job_id: uuid.UUID) -> VendorEarning | None:
        return await self.session.scalar(
            select(VendorEarning).where(VendorEarning.job_id == job_id)
        )

    async def active_plan(
        self,
        vendor_id: uuid.UUID,
        at: datetime | None = None,
    ) -> VendorCompensationPlan | None:
        at = at or datetime.now(UTC)
        return await self.session.scalar(
            select(VendorCompensationPlan)
            .where(
                VendorCompensationPlan.vendor_id == vendor_id,
                VendorCompensationPlan.active.is_(True),
                VendorCompensationPlan.effective_from <= at,
                (VendorCompensationPlan.effective_to.is_(None))
                | (VendorCompensationPlan.effective_to > at),
            )
            .order_by(VendorCompensationPlan.effective_from.desc())
            .limit(1)
        )

    async def service_rate(
        self,
        plan_id: uuid.UUID,
        service_id: uuid.UUID,
    ) -> VendorServiceCompensation | None:
        return await self.session.scalar(
            select(VendorServiceCompensation).where(
                VendorServiceCompensation.plan_id == plan_id,
                VendorServiceCompensation.service_id == service_id,
            )
        )

    async def available_earnings(
        self,
        currency: str,
        vendor_id: uuid.UUID | None = None,
        lock: bool = False,
    ) -> list[VendorEarning]:
        query = (
            select(VendorEarning)
            .where(
                VendorEarning.status == EarningStatus.AVAILABLE,
                VendorEarning.available_at <= datetime.now(UTC),
                VendorEarning.currency == currency,
            )
            .order_by(VendorEarning.available_at)
        )
        if vendor_id:
            query = query.where(VendorEarning.vendor_id == vendor_id)
        if lock:
            query = query.with_for_update(skip_locked=True)
        return list((await self.session.scalars(query)).all())

    async def get_batch(
        self,
        batch_id: uuid.UUID,
        lock: bool = False,
    ) -> PayoutBatch | None:
        query = select(PayoutBatch).where(PayoutBatch.id == batch_id)
        if lock:
            query = query.with_for_update()
        return await self.session.scalar(query)
