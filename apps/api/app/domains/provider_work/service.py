import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.domains.auth.models import User
from app.domains.catalog.models import Service
from app.domains.dispatch.models import DispatchOffer, OfferStatus
from app.domains.dispatch.service import DispatchService
from app.domains.jobs.models import Job, JobStatus
from app.domains.workforce.provider_scope import provider_vendor

from .schemas import (
    ProviderJobList,
    ProviderJobRead,
    ProviderOfferDecision,
    ProviderOfferList,
    ProviderOfferRead,
)


class ProviderWorkService:
    """Read-only job/offer visibility plus delegation to the existing offer authority."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_jobs(
        self,
        user: User,
        *,
        status: JobStatus | None,
        limit: int,
        offset: int,
    ) -> ProviderJobList:
        vendor = await provider_vendor(self.session, user)
        filters = [Job.vendor_id == vendor.id]
        if status:
            filters.append(Job.status == status)
        rows = (
            await self.session.execute(
                select(Job, Service.name)
                .outerjoin(Service, Service.id == Job.service_id)
                .where(*filters)
                .order_by(Job.scheduled_start.desc(), Job.id)
                .limit(limit)
                .offset(offset)
            )
        ).all()
        total = await self.session.scalar(
            select(func.count()).select_from(Job).where(*filters)
        )
        return ProviderJobList(
            items=[
                ProviderJobRead(
                    id=job.id,
                    booking_id=job.booking_id,
                    service_id=job.service_id,
                    service_name=service_name,
                    status=job.status,
                    scheduled_start=job.scheduled_start,
                    scheduled_end=job.scheduled_end,
                    worker_id=job.worker_id,
                    completed_at=job.completed_at,
                    updated_at=job.updated_at,
                )
                for job, service_name in rows
            ],
            total=int(total or 0),
        )

    async def list_offers(
        self,
        user: User,
        *,
        status: OfferStatus | None,
        limit: int,
        offset: int,
    ) -> ProviderOfferList:
        vendor = await provider_vendor(self.session, user)
        filters = [DispatchOffer.vendor_id == vendor.id]
        if status:
            filters.append(DispatchOffer.status == status)
        rows = (
            await self.session.execute(
                select(DispatchOffer, Job, Service.name)
                .outerjoin(Job, Job.id == DispatchOffer.job_id)
                .outerjoin(Service, Service.id == Job.service_id)
                .where(*filters)
                .order_by(DispatchOffer.created_at.desc(), DispatchOffer.id)
                .limit(limit)
                .offset(offset)
            )
        ).all()
        total = await self.session.scalar(
            select(func.count()).select_from(DispatchOffer).where(*filters)
        )
        return ProviderOfferList(
            items=[
                self._offer_read(offer, job, service_name)
                for offer, job, service_name in rows
            ],
            total=int(total or 0),
        )

    async def decide_offer(
        self,
        offer_id: uuid.UUID,
        user: User,
        decision: ProviderOfferDecision,
    ) -> ProviderOfferRead:
        vendor = await provider_vendor(self.session, user, write=True)
        owned = await self.session.scalar(
            select(DispatchOffer.id).where(
                DispatchOffer.id == offer_id,
                DispatchOffer.vendor_id == vendor.id,
            )
        )
        if not owned:
            # Another provider's offer is indistinguishable from a missing one.
            raise DomainError("OFFER_NOT_FOUND", "Offer not found.", 404)
        offer = await DispatchService(self.session).decide_offer(
            offer_id,
            vendor.id,
            decision.accept,
            decision.worker_id,
            user.id,
        )
        job = await self.session.get(Job, offer.job_id)
        service_name = (
            await self.session.scalar(select(Service.name).where(Service.id == job.service_id))
            if job
            else None
        )
        return self._offer_read(offer, job, service_name)

    @staticmethod
    def _offer_read(
        offer: DispatchOffer, job: Job | None, service_name: str | None
    ) -> ProviderOfferRead:
        return ProviderOfferRead(
            id=offer.id,
            job_id=offer.job_id,
            worker_id=offer.worker_id,
            status=offer.status,
            round=offer.round,
            expires_at=offer.expires_at,
            responded_at=offer.responded_at,
            created_at=offer.created_at,
            job_status=job.status if job else None,
            service_id=job.service_id if job else None,
            service_name=service_name,
            scheduled_start=job.scheduled_start if job else None,
            scheduled_end=job.scheduled_end if job else None,
        )
