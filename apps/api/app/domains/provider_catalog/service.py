import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.domains.auth.models import User
from app.domains.catalog.models import Service
from app.domains.common.clock import Clock, SystemClock
from app.domains.common.outbox import AuditLog, EventStatus, IntegrationEvent
from app.domains.workforce.models import (
    ProviderApplicationStatus,
    Vendor,
    VendorStatus,
    Worker,
)

from .models import ApprovalStatus, ProviderService, ProviderSkill, SkillDefinition
from .repository import ProviderCatalogRepository
from .schemas import (
    CatalogSkillList,
    CatalogSkillRead,
    ProviderServiceCreate,
    ProviderServiceList,
    ProviderServiceRead,
    ProviderServiceUpdate,
    ProviderSkillCreate,
    ProviderSkillList,
    ProviderSkillRead,
    RequiredSkillRead,
)


class ProviderCatalogService:
    """Provider-owned service and professional-skill selection workflow."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.session = session
        self.clock = clock or SystemClock()
        self.repository = ProviderCatalogRepository(session)

    async def list_services(
        self,
        user: User,
        *,
        include_inactive: bool,
    ) -> ProviderServiceList:
        vendor = await self._owned_vendor(user)
        rows = await self.repository.list_provider_services(
            vendor.id,
            include_inactive=include_inactive,
        )
        return ProviderServiceList(
            items=[await self._service_read(item) for item in rows],
            total=len(rows),
        )

    async def add_service(
        self,
        user: User,
        command: ProviderServiceCreate,
        *,
        correlation_id: str | None = None,
    ) -> ProviderServiceRead:
        vendor = await self._owned_vendor(user, lock=True, write=True)
        catalog_service = await self.repository.active_service(command.service_id)
        if not catalog_service:
            raise DomainError("SERVICE_NOT_FOUND", "Catalog service not found.", 404)
        existing = await self.repository.provider_service_by_catalog(
            vendor.id,
            catalog_service.id,
            lock=True,
        )
        if existing and existing.active:
            raise DomainError(
                "PROVIDER_SERVICE_CONFLICT",
                "Provider already selected this catalog service.",
                409,
            )
        status = self._selection_status(
            vendor,
            catalog_service.provider_approval_required,
        )
        if existing:
            existing.active = True
            existing.display_order = command.display_order
            if existing.status == ApprovalStatus.REJECTED:
                existing.status = status
                existing.rejection_reason = None
                existing.reviewed_by = None
                existing.reviewed_at = None
            existing.version += 1
            record = existing
        else:
            record = ProviderService(
                vendor_id=vendor.id,
                service_id=catalog_service.id,
                status=status,
                active=True,
                display_order=command.display_order,
                version=1,
            )
            self.session.add(record)
            await self.session.flush()
        await self._sync_application(vendor.id)
        self._record_change(
            actor=user,
            action="provider.service.select",
            aggregate_type="provider_service",
            aggregate_id=record.id,
            aggregate_version=record.version,
            metadata={
                "vendor_id": str(vendor.id),
                "service_id": str(catalog_service.id),
                "status": record.status.value,
                "correlation_id": correlation_id,
            },
        )
        await self.session.commit()
        await self.session.refresh(record)
        return await self._service_read(record)

    async def update_service(
        self,
        provider_service_id: uuid.UUID,
        user: User,
        command: ProviderServiceUpdate,
        *,
        expected_version: int,
        correlation_id: str | None = None,
    ) -> ProviderServiceRead:
        vendor = await self._owned_vendor(user, lock=True, write=True)
        record = await self.repository.provider_service(
            vendor.id,
            provider_service_id,
            lock=True,
        )
        if not record:
            raise DomainError(
                "PROVIDER_SERVICE_NOT_FOUND",
                "Provider service not found.",
                404,
            )
        self._require_version(record.version, expected_version, "provider service")
        if command.active:
            # Only (re)activating a selection needs the catalog service to still be
            # active -- withdrawing one (active=False) must keep working even after
            # BREERO deactivates the underlying catalog service, same as
            # remove_service already does with no such check.
            catalog_service = await self.repository.active_service(record.service_id)
            if not catalog_service:
                raise DomainError("SERVICE_NOT_FOUND", "Catalog service not found.", 404)
            record.active = True
            if record.status == ApprovalStatus.REJECTED:
                record.status = self._selection_status(
                    vendor,
                    catalog_service.provider_approval_required,
                )
                record.rejection_reason = None
                record.reviewed_by = None
                record.reviewed_at = None
        elif command.active is False:
            record.active = False
        if command.display_order is not None:
            record.display_order = command.display_order
        record.version += 1
        await self._sync_application(vendor.id)
        self._record_change(
            actor=user,
            action="provider.service.update",
            aggregate_type="provider_service",
            aggregate_id=record.id,
            aggregate_version=record.version,
            metadata={
                "vendor_id": str(vendor.id),
                "service_id": str(record.service_id),
                "active": record.active,
                "status": record.status.value,
                "correlation_id": correlation_id,
            },
        )
        await self.session.commit()
        await self.session.refresh(record)
        return await self._service_read(record)

    async def remove_service(
        self,
        provider_service_id: uuid.UUID,
        user: User,
        *,
        expected_version: int,
        correlation_id: str | None = None,
    ) -> None:
        vendor = await self._owned_vendor(user, lock=True, write=True)
        record = await self.repository.provider_service(
            vendor.id,
            provider_service_id,
            lock=True,
        )
        if not record:
            raise DomainError(
                "PROVIDER_SERVICE_NOT_FOUND",
                "Provider service not found.",
                404,
            )
        self._require_version(record.version, expected_version, "provider service")
        if record.active:
            record.active = False
            record.version += 1
            await self._sync_application(vendor.id)
            self._record_change(
                actor=user,
                action="provider.service.remove",
                aggregate_type="provider_service",
                aggregate_id=record.id,
                aggregate_version=record.version,
                metadata={
                    "vendor_id": str(vendor.id),
                    "service_id": str(record.service_id),
                    "correlation_id": correlation_id,
                },
            )
            await self.session.commit()

    async def skill_catalog(self) -> CatalogSkillList:
        rows = await self.repository.active_skills()
        return CatalogSkillList(
            items=[self._catalog_skill(skill) for skill in rows],
            total=len(rows),
        )

    async def list_skills(
        self,
        user: User,
        *,
        worker_id: uuid.UUID | None,
        include_inactive: bool,
    ) -> ProviderSkillList:
        vendor = await self._owned_vendor(user)
        if worker_id and not await self.repository.worker(vendor.id, worker_id):
            raise DomainError("WORKER_NOT_FOUND", "Provider professional not found.", 404)
        rows = await self.repository.list_provider_skills(
            vendor.id,
            worker_id=worker_id,
            include_inactive=include_inactive,
        )
        return ProviderSkillList(
            items=[await self._skill_read(item) for item in rows],
            total=len(rows),
        )

    async def add_skill(
        self,
        user: User,
        command: ProviderSkillCreate,
        *,
        correlation_id: str | None = None,
    ) -> ProviderSkillRead:
        vendor = await self._owned_vendor(user, lock=True, write=True)
        worker = await self._selected_worker(vendor, user, command.worker_id, lock=True)
        skill = await self.repository.active_skill(command.skill_id)
        if not skill:
            raise DomainError("SKILL_NOT_FOUND", "Catalog skill not found.", 404)
        existing = await self.repository.provider_skill_by_catalog(
            worker.id,
            skill.id,
            lock=True,
        )
        if existing and existing.active:
            raise DomainError(
                "PROVIDER_SKILL_CONFLICT",
                "Professional already selected this catalog skill.",
                409,
            )
        status = self._selection_status(vendor, skill.provider_approval_required)
        if existing:
            existing.active = True
            if existing.status == ApprovalStatus.REJECTED:
                existing.status = status
                existing.rejection_reason = None
                existing.reviewed_by = None
                existing.reviewed_at = None
            existing.version += 1
            record = existing
        else:
            record = ProviderSkill(
                vendor_id=vendor.id,
                worker_id=worker.id,
                skill_id=skill.id,
                status=status,
                active=True,
                version=1,
            )
            self.session.add(record)
            await self.session.flush()
        await self._sync_application(vendor.id)
        await self._sync_legacy_worker_skills(worker)
        self._record_change(
            actor=user,
            action="provider.skill.select",
            aggregate_type="provider_skill",
            aggregate_id=record.id,
            aggregate_version=record.version,
            metadata={
                "vendor_id": str(vendor.id),
                "worker_id": str(worker.id),
                "skill_id": str(skill.id),
                "status": record.status.value,
                "correlation_id": correlation_id,
            },
        )
        await self.session.commit()
        await self.session.refresh(record)
        return await self._skill_read(record)

    async def remove_skill(
        self,
        provider_skill_id: uuid.UUID,
        user: User,
        *,
        expected_version: int,
        correlation_id: str | None = None,
    ) -> None:
        vendor = await self._owned_vendor(user, lock=True, write=True)
        record = await self.repository.provider_skill(
            vendor.id,
            provider_skill_id,
            lock=True,
        )
        if not record:
            raise DomainError(
                "PROVIDER_SKILL_NOT_FOUND",
                "Provider skill not found.",
                404,
            )
        self._require_version(record.version, expected_version, "provider skill")
        worker = await self.repository.worker(vendor.id, record.worker_id, lock=True)
        if record.active:
            record.active = False
            record.version += 1
            await self._sync_application(vendor.id)
            if worker:
                await self._sync_legacy_worker_skills(worker)
            self._record_change(
                actor=user,
                action="provider.skill.remove",
                aggregate_type="provider_skill",
                aggregate_id=record.id,
                aggregate_version=record.version,
                metadata={
                    "vendor_id": str(vendor.id),
                    "worker_id": str(record.worker_id),
                    "skill_id": str(record.skill_id),
                    "correlation_id": correlation_id,
                },
            )
            await self.session.commit()

    async def _owned_vendor(
        self,
        user: User,
        *,
        lock: bool = False,
        write: bool = False,
    ) -> Vendor:
        vendor = await self.repository.vendor_for_user(user, lock=lock)
        if not vendor:
            raise DomainError(
                "PROVIDER_SCOPE_REQUIRED",
                "Account is not linked to a provider organization.",
                403,
            )
        if write and vendor.status in {VendorStatus.SUSPENDED, VendorStatus.REJECTED}:
            raise DomainError(
                "PROVIDER_NOT_EDITABLE",
                "Provider organization cannot be changed in its current state.",
                409,
            )
        if write:
            application = await self.repository.application(vendor.id)
            if application and application.status == ProviderApplicationStatus.PENDING:
                raise DomainError(
                    "PROVIDER_APPLICATION_UNDER_REVIEW",
                    "Service and skill selections are locked while the provider "
                    "application is under review.",
                    409,
                )
        return vendor

    async def _selected_worker(
        self,
        vendor: Vendor,
        user: User,
        worker_id: uuid.UUID | None,
        *,
        lock: bool,
    ) -> Worker:
        worker = (
            await self.repository.worker(vendor.id, worker_id, lock=lock)
            if worker_id
            else await self.repository.primary_worker(
                vendor.id,
                user.id,
                lock=lock,
            )
        )
        if not worker:
            raise DomainError(
                "WORKER_NOT_FOUND",
                "Provider professional not found.",
                404,
            )
        return worker

    async def _sync_application(self, vendor_id: uuid.UUID) -> None:
        application = await self.repository.application(vendor_id, lock=True)
        if not application:
            return
        services = await self.repository.list_provider_services(
            vendor_id,
            include_inactive=False,
        )
        skills = await self.repository.list_provider_skills(
            vendor_id,
            worker_id=None,
            include_inactive=False,
        )
        application.services = [str(item.service_id) for item in services]
        application.skills = [str(item.skill_id) for item in skills]
        application.version += 1

    async def _sync_legacy_worker_skills(self, worker: Worker) -> None:
        rows = await self.repository.list_provider_skills(
            worker.vendor_id,
            worker_id=worker.id,
            include_inactive=False,
        )
        keys: list[str] = []
        for row in rows:
            skill = await self.session.get(SkillDefinition, row.skill_id)
            if skill:
                keys.append(skill.key)
        worker.skills = list(dict.fromkeys(keys))

    async def _service_read(self, record: ProviderService) -> ProviderServiceRead:
        service = await self.session.get(Service, record.service_id)
        if not service:
            raise DomainError("SERVICE_NOT_FOUND", "Catalog service not found.", 404)
        required_skills = [
            RequiredSkillRead(
                id=skill.id,
                key=skill.key,
                name=skill.name,
                category=skill.category,
                description=skill.description,
                provider_approval_required=skill.provider_approval_required,
                required=requirement.required,
            )
            for requirement, skill in await self.repository.required_skills(service.id)
        ]
        return ProviderServiceRead(
            id=record.id,
            vendor_id=record.vendor_id,
            service_id=service.id,
            service_slug=service.slug,
            service_name=service.name,
            service_category=service.category,
            status=record.status,
            active=record.active,
            display_order=record.display_order,
            provider_approval_required=service.provider_approval_required,
            required_skills=required_skills,
            version=record.version,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    async def _skill_read(self, record: ProviderSkill) -> ProviderSkillRead:
        skill = await self.session.get(SkillDefinition, record.skill_id)
        if not skill:
            raise DomainError("SKILL_NOT_FOUND", "Catalog skill not found.", 404)
        return ProviderSkillRead(
            id=record.id,
            vendor_id=record.vendor_id,
            worker_id=record.worker_id,
            skill=self._catalog_skill(skill),
            status=record.status,
            active=record.active,
            version=record.version,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    @staticmethod
    def _catalog_skill(skill: SkillDefinition) -> CatalogSkillRead:
        return CatalogSkillRead(
            id=skill.id,
            key=skill.key,
            name=skill.name,
            category=skill.category,
            description=skill.description,
            provider_approval_required=skill.provider_approval_required,
        )

    @staticmethod
    def _selection_status(
        vendor: Vendor,
        provider_approval_required: bool,
    ) -> ApprovalStatus:
        if vendor.status == VendorStatus.ACTIVE and not provider_approval_required:
            return ApprovalStatus.APPROVED
        return ApprovalStatus.PENDING

    @staticmethod
    def _require_version(
        current: int,
        expected: int,
        resource_name: str,
    ) -> None:
        if current != expected:
            raise DomainError(
                "VERSION_CONFLICT",
                f"{resource_name.title()} changed since it was loaded.",
                409,
                fields={"current_version": current},
            )

    def _record_change(
        self,
        *,
        actor: User,
        action: str,
        aggregate_type: str,
        aggregate_id: uuid.UUID,
        aggregate_version: int,
        metadata: dict[str, Any],
    ) -> None:
        now = self.clock.now()
        self.session.add(
            AuditLog(
                actor_id=actor.id,
                actor_type="provider",
                action=action,
                resource_type=aggregate_type,
                resource_id=aggregate_id,
                metadata_json=metadata,
                created_at=now,
            )
        )
        prefix, verb = action.rsplit(".", 1)
        verb_past = {"select": "selected", "update": "updated", "remove": "removed"}.get(
            verb, verb + "d"
        )
        self.session.add(
            IntegrationEvent(
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                aggregate_version=aggregate_version,
                event_type=f"{prefix.replace('.', '_')}_{verb_past}",
                idempotency_key=(
                    f"{aggregate_type}:{aggregate_id}:"
                    f"{aggregate_version}:{action}"
                ),
                payload={
                    "aggregate_id": str(aggregate_id),
                    "actor_user_id": str(actor.id),
                    **metadata,
                },
                # PENDING, not PENDING_CONFIGURATION: these events have no
                # external-adapter dependency (not "breero."-prefixed, not an email
                # notification) to gate on. PENDING_CONFIGURATION is only ever
                # promoted by OutboxService.activate_pending_configuration(), which
                # is called with aggregate_type="public_submission" in
                # workers/tasks.py and never matches "provider_service"/
                # "provider_skill" -- using that status here left the same class of
                # bug fixed for onboarding_service.py's events elsewhere in this PR
                # chain: the event would be permanently stuck and never delivered.
                status=EventStatus.PENDING,
                attempts=0,
                available_at=now,
            )
        )
