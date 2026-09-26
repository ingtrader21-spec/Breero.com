from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.domains.auth.models import User
from app.domains.common.outbox import AuditLog

from .models import Vendor, Worker, WorkerStatus
from .provider_scope import provider_vendor
from .schemas import ProviderWorkerCreate, ProviderWorkerList, ProviderWorkerRead

MAX_PROVIDER_WORKERS = 200


def worker_read(vendor: Vendor, worker: Worker) -> ProviderWorkerRead:
    return ProviderWorkerRead(
        id=worker.id,
        first_name=worker.first_name,
        last_name=worker.last_name,
        email=worker.email,
        phone=worker.phone,
        status=worker.status,
        available=worker.available,
        skills=list(worker.skills or []),
        has_account=worker.user_id is not None,
        is_account_owner=(
            worker.user_id is not None and worker.user_id == vendor.owner_user_id
        ),
    )


class ProviderTeamService:
    """Team roster for the principal's own provider organization only."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_workers(self, user: User) -> ProviderWorkerList:
        vendor = await provider_vendor(self.session, user)
        rows = list(
            (
                await self.session.scalars(
                    select(Worker)
                    .where(Worker.vendor_id == vendor.id)
                    .order_by(Worker.last_name, Worker.first_name, Worker.id)
                )
            ).all()
        )
        return ProviderWorkerList(
            items=[worker_read(vendor, item) for item in rows],
            total=len(rows),
        )

    async def add_worker(self, user: User, command: ProviderWorkerCreate) -> ProviderWorkerRead:
        vendor = await provider_vendor(self.session, user, lock=True, write=True)
        count = await self.session.scalar(
            select(func.count()).select_from(Worker).where(Worker.vendor_id == vendor.id)
        )
        if int(count or 0) >= MAX_PROVIDER_WORKERS:
            raise DomainError(
                "WORKER_LIMIT_REACHED",
                f"A provider may list at most {MAX_PROVIDER_WORKERS} professionals.",
                409,
            )
        # New professionals are recorded as INVITED and unavailable. No invitation is
        # sent and no account is linked; BREERO operations activate them after review.
        worker = Worker(
            vendor_id=vendor.id,
            user_id=None,
            first_name=command.first_name,
            last_name=command.last_name,
            email=str(command.email).strip().lower(),
            phone=command.phone,
            status=WorkerStatus.INVITED,
            skills=[],
            available=False,
        )
        self.session.add(worker)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            raise DomainError(
                "WORKER_CONFLICT",
                "A professional with this email already exists for your organization.",
                409,
            ) from exc
        self.session.add(
            AuditLog(
                actor_id=user.id,
                actor_type="provider",
                action="provider.worker.create",
                resource_type="worker",
                resource_id=worker.id,
                metadata_json={"vendor_id": str(vendor.id)},
                created_at=datetime.now(UTC),
            )
        )
        await self.session.commit()
        await self.session.refresh(worker)
        return worker_read(vendor, worker)
