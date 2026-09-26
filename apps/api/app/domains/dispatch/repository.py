import uuid
from datetime import datetime
from typing import cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.workforce.models import Vendor, VendorStatus, Worker, WorkerStatus

from .models import Assignment, AssignmentStatus, DispatchOffer, OfferStatus


class DispatchRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def candidate_workers(self, capabilities: list[str], limit=20, worker_id=None):
        query = (
            select(Vendor, Worker)
            .join(Worker, Worker.vendor_id == Vendor.id)
            .where(Vendor.status == VendorStatus.ACTIVE)
            .where(Worker.status == WorkerStatus.ACTIVE, Worker.available.is_(True))
            .limit(limit)
        )
        if capabilities:
            query = query.where(Vendor.capabilities.contains(capabilities))
        if worker_id is not None:
            query = query.where(Worker.id == worker_id)
        return list((await self.session.execute(query)).all())

    async def get_offer(self, offer_id: uuid.UUID, lock=False) -> DispatchOffer | None:
        query = select(DispatchOffer).where(DispatchOffer.id == offer_id)
        if lock:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def offers_for_job(self, job_id: uuid.UUID) -> list[DispatchOffer]:
        return list(
            (
                await self.session.scalars(
                    select(DispatchOffer)
                    .where(DispatchOffer.job_id == job_id)
                    .order_by(DispatchOffer.score.desc())
                )
            ).all()
        )

    async def active_assignment(
        self, job_id: uuid.UUID, lock: bool = False
    ) -> Assignment | None:
        query = select(Assignment).where(
            Assignment.job_id == job_id, Assignment.status == AssignmentStatus.ACTIVE
        )
        if lock:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def dispatchable_worker(
        self, worker_id: uuid.UUID, vendor_id: uuid.UUID
    ) -> Worker | None:
        return await self.session.scalar(
            select(Worker)
            .join(Vendor, Vendor.id == Worker.vendor_id)
            .where(
                Worker.id == worker_id,
                Worker.vendor_id == vendor_id,
                Worker.status == WorkerStatus.ACTIVE,
                Worker.available.is_(True),
                Vendor.status == VendorStatus.ACTIVE,
            )
        )

    async def expire_due(self, now: datetime) -> int:
        result = await self.session.execute(
            update(DispatchOffer)
            .where(DispatchOffer.status == OfferStatus.PENDING, DispatchOffer.expires_at <= now)
            .values(status=OfferStatus.EXPIRED)
        )
        return cast(CursorResult, result).rowcount or 0
