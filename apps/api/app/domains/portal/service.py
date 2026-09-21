from __future__ import annotations

import enum
from datetime import UTC, datetime, timedelta
from typing import Any, Sequence

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.domains.auth.models import User
from app.domains.booking.models import Booking, Customer, ServiceArea
from app.domains.capabilities.service import public_capabilities
from app.domains.common.outbox import AuditLog, IntegrationEvent
from app.domains.finance.models import EarningStatus, PayoutBatch, PayoutStatus, VendorEarning
from app.domains.finance.schemas import EarningRead, PayoutBatchRead
from app.domains.geography.models import ServiceZonePostalCode
from app.domains.jobs.models import Job, JobStatus
from app.domains.jobs.schemas import JobRead
from app.domains.provider_catalog.models import ProviderService, ProviderSkill
from app.domains.provider_catalog.repository import ProviderCatalogRepository
from app.domains.public_submissions.models import PublicSubmission
from app.domains.workforce.models import (
    ProviderApplication,
    ProviderCredential,
    Vendor,
    Worker,
)
from app.domains.workforce.schemas import (
    ProviderApplicationRead,
    ProviderCredentialRead,
    VendorRead,
    WorkerRead,
)

from .schemas import (
    AdminOverview,
    AuditEventList,
    AuditEventRead,
    EffectiveCapabilities,
    MoneyStatus,
    OperationsOverview,
    ProviderCredentialList,
    ProviderEarningList,
    ProviderJobList,
    ProviderOverview,
    ProviderPayoutBatchList,
    ProviderWorkerList,
    StatusCount,
)


class PortalReadService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.provider_repository = ProviderCatalogRepository(session)

    @staticmethod
    def capabilities() -> EffectiveCapabilities:
        public = public_capabilities(settings)
        return EffectiveCapabilities(
            request_intake=public.request_intake,
            scheduling=settings.scheduling_enabled,
            instant_booking=public.instant_booking,
            online_payments=public.online_payments,
            payouts=settings.payout_enabled,
            automatic_assignment=public.automatic_assignment,
            provider_self_service=public.provider_self_service,
            marketplace_matching=public.marketplace_matching,
            messaging=public.messaging,
            reviews=public.reviews,
            middleware_delivery=settings.middleware_enabled,
            transactional_email_mode=settings.transactional_email_mode,
            transactional_sms_mode=settings.transactional_sms_mode,
        )

    @staticmethod
    def _status_name(value: object) -> str:
        if isinstance(value, enum.Enum):
            return str(value.value)
        return str(value)

    @classmethod
    def _status_counts(cls, rows: Sequence[Any]) -> list[StatusCount]:
        return [
            StatusCount(status=cls._status_name(row[0]), count=int(row[1]))
            for row in rows
        ]

    @classmethod
    def _money_statuses(cls, rows: Sequence[Any]) -> list[MoneyStatus]:
        return [
            MoneyStatus(
                status=cls._status_name(row[0]),
                currency=str(row[1]),
                count=int(row[2]),
                amount_minor=int(row[3] or 0),
            )
            for row in rows
        ]

    async def _provider(self, user: User) -> Vendor:
        vendor = await self.provider_repository.vendor_for_user(user)
        if not vendor:
            raise HTTPException(403, "Account is not linked to a provider organization")
        return vendor

    async def provider_overview(self, user: User) -> ProviderOverview:
        vendor = await self._provider(user)
        application = await self.session.scalar(
            select(ProviderApplication).where(ProviderApplication.vendor_id == vendor.id)
        )
        workers_total = int(
            await self.session.scalar(
                select(func.count()).select_from(Worker).where(Worker.vendor_id == vendor.id)
            )
            or 0
        )
        workers_available = int(
            await self.session.scalar(
                select(func.count())
                .select_from(Worker)
                .where(Worker.vendor_id == vendor.id, Worker.available.is_(True))
            )
            or 0
        )
        services_active = int(
            await self.session.scalar(
                select(func.count())
                .select_from(ProviderService)
                .where(ProviderService.vendor_id == vendor.id, ProviderService.active.is_(True))
            )
            or 0
        )
        skills_active = int(
            await self.session.scalar(
                select(func.count())
                .select_from(ProviderSkill)
                .where(ProviderSkill.vendor_id == vendor.id, ProviderSkill.active.is_(True))
            )
            or 0
        )
        credentials_total = int(
            await self.session.scalar(
                select(func.count())
                .select_from(ProviderCredential)
                .where(ProviderCredential.vendor_id == vendor.id)
            )
            or 0
        )
        credentials_verified = int(
            await self.session.scalar(
                select(func.count())
                .select_from(ProviderCredential)
                .where(
                    ProviderCredential.vendor_id == vendor.id,
                    ProviderCredential.verified.is_(True),
                )
            )
            or 0
        )
        expiring_on = datetime.now(UTC).date() + timedelta(days=30)
        credentials_expiring_soon = int(
            await self.session.scalar(
                select(func.count())
                .select_from(ProviderCredential)
                .where(
                    ProviderCredential.vendor_id == vendor.id,
                    ProviderCredential.expires_on <= expiring_on,
                )
            )
            or 0
        )
        job_rows = (
            await self.session.execute(
                select(Job.status, func.count(Job.id))
                .where(Job.vendor_id == vendor.id)
                .group_by(Job.status)
                .order_by(Job.status)
            )
        ).all()
        earning_rows = (
            await self.session.execute(
                select(
                    VendorEarning.status,
                    VendorEarning.currency,
                    func.count(VendorEarning.id),
                    func.coalesce(
                        func.sum(
                            VendorEarning.net_minor + VendorEarning.adjustment_total_minor
                        ),
                        0,
                    ),
                )
                .where(VendorEarning.vendor_id == vendor.id)
                .group_by(VendorEarning.status, VendorEarning.currency)
                .order_by(VendorEarning.status, VendorEarning.currency)
            )
        ).all()
        recent_jobs = list(
            (
                await self.session.scalars(
                    select(Job)
                    .where(Job.vendor_id == vendor.id)
                    .order_by(Job.scheduled_start.desc(), Job.id)
                    .limit(10)
                )
            ).all()
        )
        recent_earnings = list(
            (
                await self.session.scalars(
                    select(VendorEarning)
                    .where(VendorEarning.vendor_id == vendor.id)
                    .order_by(VendorEarning.created_at.desc(), VendorEarning.id)
                    .limit(10)
                )
            ).all()
        )
        recent_batches = await self._provider_batches(vendor.id, None, 10, 0)
        return ProviderOverview(
            vendor=VendorRead.model_validate(vendor),
            application=(
                ProviderApplicationRead.model_validate(application) if application else None
            ),
            capabilities=self.capabilities(),
            workers_total=workers_total,
            workers_available=workers_available,
            services_active=services_active,
            skills_active=skills_active,
            credentials_total=credentials_total,
            credentials_verified=credentials_verified,
            credentials_expiring_soon=credentials_expiring_soon,
            jobs=self._status_counts(job_rows),
            earnings=self._money_statuses(earning_rows),
            recent_jobs=[JobRead.model_validate(item) for item in recent_jobs],
            recent_earnings=[EarningRead.model_validate(item) for item in recent_earnings],
            recent_payout_batches=[
                PayoutBatchRead.model_validate(item) for item in recent_batches
            ],
        )

    async def provider_jobs(
        self,
        user: User,
        status: JobStatus | None,
        limit: int,
        offset: int,
    ) -> ProviderJobList:
        vendor = await self._provider(user)
        filters = [Job.vendor_id == vendor.id]
        if status:
            filters.append(Job.status == status)
        items = list(
            (
                await self.session.scalars(
                    select(Job)
                    .where(*filters)
                    .order_by(Job.scheduled_start.desc(), Job.id)
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        total = int(
            await self.session.scalar(
                select(func.count()).select_from(Job).where(*filters)
            )
            or 0
        )
        return ProviderJobList(
            items=[JobRead.model_validate(item) for item in items],
            total=total,
        )

    async def provider_workers(
        self,
        user: User,
        limit: int,
        offset: int,
    ) -> ProviderWorkerList:
        vendor = await self._provider(user)
        items = list(
            (
                await self.session.scalars(
                    select(Worker)
                    .where(Worker.vendor_id == vendor.id)
                    .order_by(Worker.created_at, Worker.id)
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        total = int(
            await self.session.scalar(
                select(func.count()).select_from(Worker).where(Worker.vendor_id == vendor.id)
            )
            or 0
        )
        return ProviderWorkerList(
            items=[WorkerRead.model_validate(item) for item in items],
            total=total,
        )

    async def provider_credentials(
        self,
        user: User,
        limit: int,
        offset: int,
    ) -> ProviderCredentialList:
        vendor = await self._provider(user)
        items = list(
            (
                await self.session.scalars(
                    select(ProviderCredential)
                    .where(ProviderCredential.vendor_id == vendor.id)
                    .order_by(ProviderCredential.expires_on, ProviderCredential.id)
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        total = int(
            await self.session.scalar(
                select(func.count())
                .select_from(ProviderCredential)
                .where(ProviderCredential.vendor_id == vendor.id)
            )
            or 0
        )
        return ProviderCredentialList(
            items=[ProviderCredentialRead.model_validate(item) for item in items],
            total=total,
        )

    async def provider_earnings(
        self,
        user: User,
        status: EarningStatus | None,
        limit: int,
        offset: int,
    ) -> ProviderEarningList:
        vendor = await self._provider(user)
        filters = [VendorEarning.vendor_id == vendor.id]
        if status:
            filters.append(VendorEarning.status == status)
        items = list(
            (
                await self.session.scalars(
                    select(VendorEarning)
                    .where(*filters)
                    .order_by(VendorEarning.created_at.desc(), VendorEarning.id)
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        total = int(
            await self.session.scalar(
                select(func.count()).select_from(VendorEarning).where(*filters)
            )
            or 0
        )
        return ProviderEarningList(
            items=[EarningRead.model_validate(item) for item in items],
            total=total,
        )

    async def _provider_batches(
        self,
        vendor_id: Any,
        status: PayoutStatus | None,
        limit: int,
        offset: int,
    ) -> list[PayoutBatchRead]:
        filters = [VendorEarning.vendor_id == vendor_id]
        if status:
            filters.append(PayoutBatch.status == status)
        rows = (await self.session.execute(
            select(
                PayoutBatch,
                func.coalesce(func.sum(VendorEarning.net_minor + VendorEarning.adjustment_total_minor), 0),
                func.count(VendorEarning.id),
            )
            .join(VendorEarning, VendorEarning.payout_batch_id == PayoutBatch.id)
            .where(*filters)
            .group_by(PayoutBatch.id)
            .order_by(PayoutBatch.created_at.desc(), PayoutBatch.id)
            .limit(limit).offset(offset)
        )).all()
        return [
            PayoutBatchRead.model_validate(batch).model_copy(
                update={"total_minor": int(total), "earning_count": int(count)}
            )
            for batch, total, count in rows
        ]

    async def provider_payout_batches(
        self,
        user: User,
        status: PayoutStatus | None,
        limit: int,
        offset: int,
    ) -> ProviderPayoutBatchList:
        vendor = await self._provider(user)
        items = await self._provider_batches(vendor.id, status, limit, offset)
        filters = [VendorEarning.vendor_id == vendor.id]
        if status:
            filters.append(PayoutBatch.status == status)
        total = int(
            await self.session.scalar(
                select(func.count(func.distinct(PayoutBatch.id)))
                .select_from(PayoutBatch)
                .join(
                    VendorEarning,
                    VendorEarning.payout_batch_id == PayoutBatch.id,
                )
                .where(*filters)
            )
            or 0
        )
        return ProviderPayoutBatchList(
            items=[PayoutBatchRead.model_validate(item) for item in items],
            total=total,
        )

    async def operations_overview(self) -> OperationsOverview:
        intake_items_total = int(
            await self.session.scalar(select(func.count()).select_from(PublicSubmission)) or 0
        )
        booking_rows = (
            await self.session.execute(
                select(Booking.status, func.count(Booking.id))
                .group_by(Booking.status)
                .order_by(Booking.status)
            )
        ).all()
        job_rows = (
            await self.session.execute(
                select(Job.status, func.count(Job.id))
                .group_by(Job.status)
                .order_by(Job.status)
            )
        ).all()
        vendor_rows = (
            await self.session.execute(
                select(Vendor.status, func.count(Vendor.id))
                .group_by(Vendor.status)
                .order_by(Vendor.status)
            )
        ).all()
        application_rows = (
            await self.session.execute(
                select(ProviderApplication.status, func.count(ProviderApplication.id))
                .group_by(ProviderApplication.status)
                .order_by(ProviderApplication.status)
            )
        ).all()
        outbox_rows = (
            await self.session.execute(
                select(IntegrationEvent.status, func.count(IntegrationEvent.id))
                .group_by(IntegrationEvent.status)
                .order_by(IntegrationEvent.status)
            )
        ).all()
        recent_jobs = list(
            (
                await self.session.scalars(
                    select(Job)
                    .order_by(Job.scheduled_start.desc(), Job.id)
                    .limit(20)
                )
            ).all()
        )
        return OperationsOverview(
            capabilities=self.capabilities(),
            intake_items_total=intake_items_total,
            bookings=self._status_counts(booking_rows),
            jobs=self._status_counts(job_rows),
            vendors=self._status_counts(vendor_rows),
            provider_applications=self._status_counts(application_rows),
            outbox=self._status_counts(outbox_rows),
            recent_jobs=[JobRead.model_validate(item) for item in recent_jobs],
        )

    async def admin_overview(self) -> AdminOverview:
        users_total = int(
            await self.session.scalar(select(func.count()).select_from(User)) or 0
        )
        users_active = int(
            await self.session.scalar(
                select(func.count()).select_from(User).where(User.is_active.is_(True))
            )
            or 0
        )
        customers_total = int(
            await self.session.scalar(select(func.count()).select_from(Customer)) or 0
        )
        service_zones_total = int(
            await self.session.scalar(select(func.count()).select_from(ServiceArea)) or 0
        )
        service_zones_active = int(
            await self.session.scalar(
                select(func.count())
                .select_from(ServiceArea)
                .where(ServiceArea.active.is_(True))
            )
            or 0
        )
        postal_codes_total = int(
            await self.session.scalar(
                select(func.count()).select_from(ServiceZonePostalCode)
            )
            or 0
        )
        postal_codes_active = int(
            await self.session.scalar(
                select(func.count())
                .select_from(ServiceZonePostalCode)
                .where(ServiceZonePostalCode.active.is_(True))
            )
            or 0
        )
        booking_rows = (
            await self.session.execute(
                select(Booking.status, func.count(Booking.id))
                .group_by(Booking.status)
                .order_by(Booking.status)
            )
        ).all()
        job_rows = (
            await self.session.execute(
                select(Job.status, func.count(Job.id))
                .group_by(Job.status)
                .order_by(Job.status)
            )
        ).all()
        vendor_rows = (
            await self.session.execute(
                select(Vendor.status, func.count(Vendor.id))
                .group_by(Vendor.status)
                .order_by(Vendor.status)
            )
        ).all()
        application_rows = (
            await self.session.execute(
                select(ProviderApplication.status, func.count(ProviderApplication.id))
                .group_by(ProviderApplication.status)
                .order_by(ProviderApplication.status)
            )
        ).all()
        earning_rows = (
            await self.session.execute(
                select(
                    VendorEarning.status,
                    VendorEarning.currency,
                    func.count(VendorEarning.id),
                    func.coalesce(
                        func.sum(
                            VendorEarning.net_minor + VendorEarning.adjustment_total_minor
                        ),
                        0,
                    ),
                )
                .group_by(VendorEarning.status, VendorEarning.currency)
                .order_by(VendorEarning.status, VendorEarning.currency)
            )
        ).all()
        payout_rows = (
            await self.session.execute(
                select(PayoutBatch.status, func.count(PayoutBatch.id))
                .group_by(PayoutBatch.status)
                .order_by(PayoutBatch.status)
            )
        ).all()
        outbox_rows = (
            await self.session.execute(
                select(IntegrationEvent.status, func.count(IntegrationEvent.id))
                .group_by(IntegrationEvent.status)
                .order_by(IntegrationEvent.status)
            )
        ).all()
        audits = list(
            (
                await self.session.scalars(
                    select(AuditLog).order_by(AuditLog.created_at.desc()).limit(25)
                )
            ).all()
        )
        return AdminOverview(
            capabilities=self.capabilities(),
            users_total=users_total,
            users_active=users_active,
            customers_total=customers_total,
            service_zones_total=service_zones_total,
            service_zones_active=service_zones_active,
            postal_codes_total=postal_codes_total,
            postal_codes_active=postal_codes_active,
            bookings=self._status_counts(booking_rows),
            jobs=self._status_counts(job_rows),
            vendors=self._status_counts(vendor_rows),
            provider_applications=self._status_counts(application_rows),
            earnings=self._money_statuses(earning_rows),
            payout_batches=self._status_counts(payout_rows),
            outbox=self._status_counts(outbox_rows),
            recent_audit=[AuditEventRead.model_validate(item) for item in audits],
        )

    async def audit_events(self, limit: int, offset: int) -> AuditEventList:
        items = list(
            (
                await self.session.scalars(
                    select(AuditLog)
                    .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        total = int(
            await self.session.scalar(select(func.count()).select_from(AuditLog)) or 0
        )
        return AuditEventList(
            items=[AuditEventRead.model_validate(item) for item in items],
            total=total,
        )
