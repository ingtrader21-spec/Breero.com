import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.models import AccessAssignment, TenantScope, User
from app.domains.catalog.models import Service
from app.domains.workforce.models import ProviderApplication, Vendor, Worker

from .models import (
    ProviderService,
    ProviderSkill,
    ServiceSkillRequirement,
    SkillDefinition,
)


class ProviderCatalogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def vendor_for_user(
        self,
        user: User,
        *,
        lock: bool = False,
    ) -> Vendor | None:
        assignment = await self.session.scalar(
            select(AccessAssignment)
            .where(
                AccessAssignment.user_id == user.id,
                AccessAssignment.brand_key == "breero",
                AccessAssignment.tenant_scope == TenantScope.vendor.value,
                AccessAssignment.vendor_id.is_not(None),
                AccessAssignment.active.is_(True),
            )
            .order_by(
                AccessAssignment.is_primary.desc(),
                AccessAssignment.created_at,
            )
            .limit(1)
        )
        if assignment and assignment.vendor_id:
            query = select(Vendor).where(Vendor.id == assignment.vendor_id)
        else:
            query = select(Vendor).where(Vendor.owner_user_id == user.id)
        if lock:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def primary_worker(
        self,
        vendor_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> Worker | None:
        query = (
            select(Worker)
            .where(
                Worker.vendor_id == vendor_id,
                Worker.user_id == user_id,
            )
            .order_by(Worker.created_at, Worker.id)
            .limit(1)
        )
        if lock:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def worker(
        self,
        vendor_id: uuid.UUID,
        worker_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> Worker | None:
        query = select(Worker).where(
            Worker.id == worker_id,
            Worker.vendor_id == vendor_id,
        )
        if lock:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def active_service(self, service_id: uuid.UUID) -> Service | None:
        return await self.session.scalar(
            select(Service).where(
                Service.id == service_id,
                Service.is_active.is_(True),
            )
        )

    async def active_skill(
        self,
        skill_id: uuid.UUID,
    ) -> SkillDefinition | None:
        return await self.session.scalar(
            select(SkillDefinition).where(
                SkillDefinition.id == skill_id,
                SkillDefinition.active.is_(True),
            )
        )

    async def active_skills(self) -> list[SkillDefinition]:
        return list(
            (
                await self.session.scalars(
                    select(SkillDefinition)
                    .where(SkillDefinition.active.is_(True))
                    .order_by(SkillDefinition.category, SkillDefinition.name)
                )
            ).all()
        )

    async def provider_service(
        self,
        vendor_id: uuid.UUID,
        provider_service_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> ProviderService | None:
        query = select(ProviderService).where(
            ProviderService.id == provider_service_id,
            ProviderService.vendor_id == vendor_id,
        )
        if lock:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def provider_service_by_catalog(
        self,
        vendor_id: uuid.UUID,
        service_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> ProviderService | None:
        query = select(ProviderService).where(
            ProviderService.vendor_id == vendor_id,
            ProviderService.service_id == service_id,
        )
        if lock:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def list_provider_services(
        self,
        vendor_id: uuid.UUID,
        *,
        include_inactive: bool,
    ) -> list[ProviderService]:
        query = select(ProviderService).where(
            ProviderService.vendor_id == vendor_id
        )
        if not include_inactive:
            query = query.where(ProviderService.active.is_(True))
        return list(
            (
                await self.session.scalars(
                    query.order_by(
                        ProviderService.display_order,
                        ProviderService.created_at,
                        ProviderService.id,
                    )
                )
            ).all()
        )

    async def required_skills(
        self,
        service_id: uuid.UUID,
    ) -> list[tuple[ServiceSkillRequirement, SkillDefinition]]:
        rows = (
            await self.session.execute(
                select(ServiceSkillRequirement, SkillDefinition)
                .join(
                    SkillDefinition,
                    SkillDefinition.id == ServiceSkillRequirement.skill_id,
                )
                .where(
                    ServiceSkillRequirement.service_id == service_id,
                    SkillDefinition.active.is_(True),
                )
                .order_by(SkillDefinition.category, SkillDefinition.name)
            )
        ).all()
        return [(row[0], row[1]) for row in rows]

    async def provider_skill(
        self,
        vendor_id: uuid.UUID,
        provider_skill_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> ProviderSkill | None:
        query = select(ProviderSkill).where(
            ProviderSkill.id == provider_skill_id,
            ProviderSkill.vendor_id == vendor_id,
        )
        if lock:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def provider_skill_by_catalog(
        self,
        worker_id: uuid.UUID,
        skill_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> ProviderSkill | None:
        query = select(ProviderSkill).where(
            ProviderSkill.worker_id == worker_id,
            ProviderSkill.skill_id == skill_id,
        )
        if lock:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def list_provider_skills(
        self,
        vendor_id: uuid.UUID,
        *,
        worker_id: uuid.UUID | None,
        include_inactive: bool,
    ) -> list[ProviderSkill]:
        query = select(ProviderSkill).where(
            ProviderSkill.vendor_id == vendor_id
        )
        if worker_id:
            query = query.where(ProviderSkill.worker_id == worker_id)
        if not include_inactive:
            query = query.where(ProviderSkill.active.is_(True))
        return list(
            (
                await self.session.scalars(
                    query.order_by(
                        ProviderSkill.worker_id,
                        ProviderSkill.created_at,
                        ProviderSkill.id,
                    )
                )
            ).all()
        )

    async def application(
        self,
        vendor_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> ProviderApplication | None:
        query = select(ProviderApplication).where(
            ProviderApplication.vendor_id == vendor_id
        )
        if lock:
            query = query.with_for_update()
        return await self.session.scalar(query)
