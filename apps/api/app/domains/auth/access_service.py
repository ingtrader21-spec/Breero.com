import uuid

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.domains.auth.models import (
    AccessAssignment,
    AccessProfile,
    AccessRole,
    Department,
    RolePermission,
    TenantScope,
    User,
    UserPermission,
    UserRole,
)
from app.domains.auth.schemas import (
    AccessAssignmentInput,
    AccessAssignmentRead,
    PortalContext,
    UserRead,
)

BRAND_KEY = "breero"
NO_ACCESS_DASHBOARD = "/access-denied"

DEFAULT_ACCESS: dict[UserRole, tuple[AccessRole, Department, TenantScope]] = {
    UserRole.customer: (AccessRole.customer, Department.customer, TenantScope.brand),
    UserRole.vendor_admin: (AccessRole.vendor_admin, Department.provider, TenantScope.brand),
    UserRole.technician: (AccessRole.technician, Department.field_service, TenantScope.brand),
    UserRole.operations: (AccessRole.operations, Department.dispatch, TenantScope.brand),
    UserRole.finance: (AccessRole.finance, Department.finance, TenantScope.brand),
    UserRole.admin: (AccessRole.admin, Department.administration, TenantScope.global_),
}

DASHBOARD_BY_ROLE: dict[AccessRole, str] = {
    AccessRole.customer: "/account",
    AccessRole.vendor_admin: "/provider",
    AccessRole.technician: "/worker",
    AccessRole.operations: "/ops",
    AccessRole.ops_manager: "/ops",
    AccessRole.support: "/support",
    AccessRole.finance: "/finance",
    AccessRole.quality: "/quality",
    AccessRole.trust_safety: "/trust-safety",
    AccessRole.sales: "/sales",
    AccessRole.marketing: "/marketing",
    AccessRole.admin: "/admin",
    AccessRole.superadmin: "/admin",
}

DEFAULT_PERMISSIONS: dict[AccessRole, set[str]] = {
    AccessRole.customer: {
        "customer.profile.read",
        "customer.profile.write",
        "customer.request.create",
        "customer.booking.read",
        "customer.quote.read",
        "customer.quote.decide",
        "customer.notifications.read",
    },
    AccessRole.vendor_admin: {
        "provider.profile.read",
        "provider.profile.write",
        "provider.credentials.read",
        "provider.worker.manage",
        "provider.availability.manage",
        "provider.jobs.read",
        "provider.quotes.manage",
        "email.domain.read",
        "email.domain.manage",
        "email.sender.read",
        "email.sender.manage",
        "email.credential.read",
        "email.credential.manage",
        "email.message.compose",
        "email.message.read",
        "email.outbox.read",
    },
    AccessRole.technician: {
        "worker.profile.read",
        "worker.schedule.read",
        "worker.availability.manage",
        "worker.jobs.read",
        "worker.jobs.update",
    },
    AccessRole.operations: {
        "ops.dispatch.read",
        "ops.dispatch.manage",
        "ops.bookings.read",
        "ops.bookings.manage",
        "ops.providers.read",
        "ops.customers.read",
        "email.message.read",
    },
    AccessRole.ops_manager: {
        "ops.dispatch.read",
        "ops.dispatch.manage",
        "ops.bookings.read",
        "ops.bookings.manage",
        "ops.providers.read",
        "ops.providers.manage",
        "ops.customers.read",
        "ops.audit.read",
        "email.message.read",
    },
    AccessRole.support: {
        "support.customers.read",
        "support.requests.read",
        "support.requests.manage",
        "support.bookings.read",
        "support.communications.read",
        "email.message.read",
    },
    AccessRole.finance: {
        "finance.ledger.read",
        "finance.payments.read",
        "finance.refunds.read",
        "finance.payouts.read",
        "finance.reconciliation.read",
        "integration.retry",
    },
    AccessRole.quality: {
        "quality.jobs.read",
        "quality.reviews.read",
        "quality.reviews.manage",
        "quality.providers.read",
    },
    AccessRole.trust_safety: {
        "trust.providers.read",
        "trust.credentials.manage",
        "trust.reviews.manage",
        "trust.audit.read",
    },
    AccessRole.sales: {
        "sales.leads.read",
        "sales.leads.manage",
        "sales.providers.read",
    },
    AccessRole.marketing: {
        "marketing.campaigns.read",
        "marketing.consents.read",
        "marketing.suppressions.read",
        "email.domain.read",
        "email.sender.read",
        "email.credential.read",
        "email.message.compose",
        "email.message.read",
    },
    AccessRole.admin: {
        "admin.access.manage",
        "admin.audit.read",
        "admin.capabilities.read",
        "admin.integrations.read",
        "email.domain.read",
        "email.domain.manage",
        "email.domain.verify",
        "email.sender.read",
        "email.sender.manage",
        "email.credential.read",
        "email.credential.manage",
        "email.message.compose",
        "email.message.read",
        "email.outbox.read",
        "email.outbox.retry",
        "integration.retry",
    },
    AccessRole.superadmin: {"*"},
}


class AccessService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def context(self, user: User, brand_key: str = BRAND_KEY) -> PortalContext:
        profile = await self.session.scalar(
            select(AccessProfile).where(
                AccessProfile.user_id == user.id,
                AccessProfile.brand_key == brand_key,
            )
        )
        rows = list(
            (
                await self.session.scalars(
                    select(AccessAssignment)
                    .where(
                        AccessAssignment.user_id == user.id,
                        AccessAssignment.brand_key == brand_key,
                        AccessAssignment.active.is_(True),
                    )
                    .order_by(AccessAssignment.is_primary.desc(), AccessAssignment.created_at)
                )
            ).all()
        )

        if profile is not None and not rows:
            return PortalContext(
                user=UserRead.model_validate(user),
                brand_key=brand_key,
                dashboard_path=NO_ACCESS_DASHBOARD,
                roles=[],
                departments=[],
                permissions=[],
                assignments=[],
                identity_mode="keycloak" if settings.keycloak_enabled else "local",
            )

        assignments = self._assignment_reads(user, rows)
        roles = list(dict.fromkeys(item.role for item in assignments))
        departments = list(dict.fromkeys(item.department for item in assignments))
        permissions = await self._permissions(user.id, brand_key, roles)
        primary = assignments[0].role
        return PortalContext(
            user=UserRead.model_validate(user),
            brand_key=brand_key,
            dashboard_path=DASHBOARD_BY_ROLE[primary],
            roles=roles,
            departments=departments,
            permissions=sorted(permissions),
            assignments=assignments,
            identity_mode="keycloak" if settings.keycloak_enabled else "local",
        )

    async def replace_assignments(
        self,
        user_id: uuid.UUID,
        brand_key: str,
        assignments: list[AccessAssignmentInput],
    ) -> PortalContext:
        user = await self.session.scalar(select(User).where(User.id == user_id).with_for_update())
        if not user:
            raise HTTPException(404, "User not found")

        profile = await self.session.scalar(
            select(AccessProfile)
            .where(
                AccessProfile.user_id == user_id,
                AccessProfile.brand_key == brand_key,
            )
            .with_for_update()
        )
        if profile is None:
            self.session.add(AccessProfile(user_id=user_id, brand_key=brand_key))
            await self.session.flush()

        await self.session.execute(
            delete(AccessAssignment).where(
                AccessAssignment.user_id == user_id,
                AccessAssignment.brand_key == brand_key,
            )
        )
        for item in assignments:
            self.session.add(
                AccessAssignment(
                    user_id=user_id,
                    brand_key=brand_key,
                    role_key=item.role.value,
                    department=item.department.value,
                    tenant_scope=item.tenant_scope.value,
                    vendor_id=item.vendor_id,
                    active=True,
                    is_primary=item.is_primary,
                )
            )
        await self.session.commit()
        return await self.context(user, brand_key)

    async def _permissions(
        self, user_id: uuid.UUID, brand_key: str, roles: list[AccessRole]
    ) -> set[str]:
        permissions: set[str] = set()
        for role in roles:
            permissions.update(DEFAULT_PERMISSIONS[role])
        role_rows = (
            await self.session.scalars(
                select(RolePermission).where(RolePermission.role_key.in_([role.value for role in roles]))
            )
        ).all()
        for role_permission in role_rows:
            if role_permission.allow:
                permissions.add(role_permission.permission)
            else:
                permissions.discard(role_permission.permission)
        user_rows = (
            await self.session.scalars(
                select(UserPermission).where(
                    UserPermission.user_id == user_id,
                    UserPermission.brand_key == brand_key,
                )
            )
        ).all()
        for user_permission in user_rows:
            if user_permission.allow:
                permissions.add(user_permission.permission)
            else:
                permissions.discard(user_permission.permission)
        return permissions

    @staticmethod
    def _assignment_reads(
        user: User, rows: list[AccessAssignment]
    ) -> list[AccessAssignmentRead]:
        if not rows:
            role, department, tenant_scope = DEFAULT_ACCESS[user.role]
            return [
                AccessAssignmentRead(
                    role=role,
                    department=department,
                    tenant_scope=tenant_scope,
                    vendor_id=None,
                    is_primary=True,
                )
            ]
        return [
            AccessAssignmentRead(
                role=AccessRole(row.role_key),
                department=Department(row.department),
                tenant_scope=TenantScope(row.tenant_scope),
                vendor_id=row.vendor_id,
                is_primary=row.is_primary,
            )
            for row in rows
        ]
