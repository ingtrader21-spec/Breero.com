"""Administrative user lifecycle for Breero-owned application state.

Keycloak remains the identity authority when enabled: this service never creates,
deletes or disables upstream identities and never reads or changes credentials.
Disabling a user here only revokes Breero portal/API access (``users.is_active``),
revokes Breero-issued refresh sessions and invalidates locally issued tokens.
"""

import uuid
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import and_, exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.errors import DomainError
from app.domains.auth.access_service import (
    BRAND_KEY,
    DEFAULT_ACCESS,
    AccessService,
)
from app.domains.auth.admin_schemas import (
    AdminUserAccessUpdate,
    AdminUserDetail,
    AdminUserList,
    AdminUserStatus,
    AdminUserSummary,
    EffectiveAccess,
    IdentityLinkSummary,
    PermissionOverride,
)
from app.domains.auth.models import (
    AccessAssignment,
    AccessProfile,
    AccessRole,
    IdentityLink,
    RolePermission,
    Session,
    User,
    UserPermission,
    UserRole,
)
from app.domains.auth.schemas import PortalContext
from app.domains.common.outbox import AuditLog
from app.domains.workforce.models import Vendor

PRIVILEGED_ROLES = frozenset({AccessRole.admin, AccessRole.superadmin})
PRIVILEGED_PERMISSIONS = frozenset({"*", "admin.access.manage"})


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _identity_authority() -> Literal["keycloak", "local"]:
    return "keycloak" if settings.keycloak_enabled else "local"


def _status(user: User) -> AdminUserStatus:
    return AdminUserStatus.active if user.is_active else AdminUserStatus.disabled


def _is_privileged(context: PortalContext) -> bool:
    return bool(PRIVILEGED_ROLES.intersection(context.roles)) or bool(
        PRIVILEGED_PERMISSIONS.intersection(context.permissions)
    )


class AdminUserService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.access = AccessService(session)

    async def list_users(
        self,
        *,
        q: str | None = None,
        role: UserRole | None = None,
        status: AdminUserStatus | None = None,
        access_role: AccessRole | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> AdminUserList:
        identity_linked = (
            exists()
            .where(IdentityLink.user_id == User.id, IdentityLink.brand_key == BRAND_KEY)
            .correlate(User)
        )
        filters = []
        if q and q.strip():
            pattern = f"%{_escape_like(q.strip().lower())}%"
            filters.append(
                or_(
                    func.lower(User.email).like(pattern, escape="\\"),
                    func.lower(User.full_name).like(pattern, escape="\\"),
                )
            )
        if role is not None:
            filters.append(User.role == role)
        if status is not None:
            filters.append(User.is_active.is_(status == AdminUserStatus.active))
        if access_role is not None:
            filters.append(self._has_access_role(access_role))

        total = await self.session.scalar(
            select(func.count()).select_from(User).where(*filters)
        )
        rows = (
            await self.session.execute(
                select(User, identity_linked.label("identity_linked"))
                .where(*filters)
                .order_by(User.created_at.desc(), User.id)
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
        ).all()
        return AdminUserList(
            items=[self._summary(user, bool(linked)) for user, linked in rows],
            total=int(total or 0),
            page=page,
            page_size=page_size,
        )

    @staticmethod
    def _has_access_role(access_role: AccessRole):
        """Mirror AccessService.context: explicit assignments, else legacy default."""
        assigned = (
            exists()
            .where(
                AccessAssignment.user_id == User.id,
                AccessAssignment.brand_key == BRAND_KEY,
                AccessAssignment.role_key == access_role.value,
                AccessAssignment.active.is_(True),
            )
            .correlate(User)
        )
        any_assignment = (
            exists()
            .where(
                AccessAssignment.user_id == User.id,
                AccessAssignment.brand_key == BRAND_KEY,
                AccessAssignment.active.is_(True),
            )
            .correlate(User)
        )
        managed = (
            exists()
            .where(AccessProfile.user_id == User.id, AccessProfile.brand_key == BRAND_KEY)
            .correlate(User)
        )
        legacy_roles = [
            legacy for legacy, (default, _, _) in DEFAULT_ACCESS.items() if default == access_role
        ]
        if not legacy_roles:
            return assigned
        return or_(
            assigned,
            and_(~any_assignment, ~managed, User.role.in_(legacy_roles)),
        )

    @staticmethod
    def _summary(user: User, identity_linked: bool) -> AdminUserSummary:
        return AdminUserSummary(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            status=_status(user),
            email_verified=user.email_verified,
            identity_linked=identity_linked,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    async def _user(self, user_id: uuid.UUID, *, lock: bool = False) -> User:
        query = select(User).where(User.id == user_id)
        if lock:
            query = query.with_for_update()
        user = await self.session.scalar(query)
        if user is None:
            raise DomainError("USER_NOT_FOUND", "User not found.", 404)
        return user

    async def detail(self, user_id: uuid.UUID, brand_key: str = BRAND_KEY) -> AdminUserDetail:
        user = await self._user(user_id)
        return await self._detail(user, brand_key)

    async def _detail(self, user: User, brand_key: str) -> AdminUserDetail:
        links = list(
            (
                await self.session.scalars(
                    select(IdentityLink)
                    .where(IdentityLink.user_id == user.id, IdentityLink.brand_key == brand_key)
                    .order_by(IdentityLink.linked_at)
                )
            ).all()
        )
        sessions = await self.session.scalar(
            select(func.count())
            .select_from(Session)
            .where(
                Session.user_id == user.id,
                Session.revoked_at.is_(None),
                Session.rotated_at.is_(None),
                Session.expires_at > datetime.now(UTC),
            )
        )
        summary = self._summary(user, bool(links))
        return AdminUserDetail(
            **summary.model_dump(),
            identity_authority=_identity_authority(),
            identity_links=[
                IdentityLinkSummary(
                    issuer=link.issuer,
                    linked_at=link.linked_at,
                    last_seen_at=link.last_seen_at,
                )
                for link in links
            ],
            active_session_count=int(sessions or 0),
            access=await self.access.context(user, brand_key),
        )

    async def effective_access(
        self, user_id: uuid.UUID, brand_key: str = BRAND_KEY
    ) -> EffectiveAccess:
        user = await self._user(user_id)
        return await self._effective_access(user, brand_key)

    async def _effective_access(self, user: User, brand_key: str) -> EffectiveAccess:
        context = await self.access.context(user, brand_key)
        managed = await self.session.scalar(
            select(
                exists().where(
                    AccessProfile.user_id == user.id, AccessProfile.brand_key == brand_key
                )
            )
        )
        role_rows = (
            await self.session.scalars(
                select(RolePermission)
                .where(RolePermission.role_key.in_([role.value for role in context.roles]))
                .order_by(RolePermission.role_key, RolePermission.permission)
            )
        ).all()
        user_rows = (
            await self.session.scalars(
                select(UserPermission)
                .where(UserPermission.user_id == user.id, UserPermission.brand_key == brand_key)
                .order_by(UserPermission.permission)
            )
        ).all()
        overrides = [
            PermissionOverride(
                permission=row.permission,
                allow=row.allow,
                source="role",
                role=AccessRole(row.role_key),
            )
            for row in role_rows
        ] + [
            PermissionOverride(permission=row.permission, allow=row.allow, source="user")
            for row in user_rows
        ]
        return EffectiveAccess(
            user_id=user.id,
            brand_key=brand_key,
            status=_status(user),
            identity_authority=_identity_authority(),
            managed_profile=bool(managed),
            access=context,
            overrides=overrides,
            effective_permissions=context.permissions if user.is_active else [],
        )

    async def _require_can_manage(self, actor: User, target: User, brand_key: str) -> None:
        if actor.id == target.id:
            raise DomainError(
                "SELF_LIFECYCLE_FORBIDDEN",
                "Administrators cannot change their own lifecycle or access state.",
                409,
            )
        target_context = await self.access.context(target, brand_key)
        if _is_privileged(target_context):
            actor_context = await self.access.context(actor, brand_key)
            if "*" not in actor_context.permissions:
                raise DomainError(
                    "SUPERADMIN_REQUIRED",
                    "Only a superadmin can change a privileged administrator.",
                    403,
                )

    def _audit(
        self, actor: User, action: str, target: User, metadata: dict[str, object]
    ) -> None:
        self.session.add(
            AuditLog(
                actor_id=actor.id,
                action=action,
                resource_type="user",
                resource_id=target.id,
                metadata_json={
                    **metadata,
                    "identity_authority": _identity_authority(),
                    # Upstream identity state is never mutated from Breero.
                    "identity_provider_action": "none",
                },
                created_at=datetime.now(UTC),
            )
        )

    async def disable(
        self,
        actor: User,
        user_id: uuid.UUID,
        reason: str,
        *,
        correlation_id: str | None = None,
    ) -> AdminUserDetail:
        target = await self._user(user_id, lock=True)
        await self._require_can_manage(actor, target, BRAND_KEY)
        if not target.is_active:
            raise DomainError("USER_ALREADY_DISABLED", "User is already disabled.", 409)
        now = datetime.now(UTC)
        target.is_active = False
        # Invalidates locally issued access tokens (cv claim) immediately.
        target.credential_version += 1
        revoked = await self.session.execute(
            update(Session)
            .where(Session.user_id == target.id, Session.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        self._audit(
            actor,
            "admin.user.disable",
            target,
            {
                "reason": reason,
                "revoked_sessions": getattr(revoked, "rowcount", 0) or 0,
                "correlation_id": correlation_id,
            },
        )
        await self.session.commit()
        await self.session.refresh(target)
        return await self._detail(target, BRAND_KEY)

    async def reactivate(
        self,
        actor: User,
        user_id: uuid.UUID,
        reason: str,
        *,
        correlation_id: str | None = None,
    ) -> AdminUserDetail:
        target = await self._user(user_id, lock=True)
        await self._require_can_manage(actor, target, BRAND_KEY)
        if target.is_active:
            raise DomainError("USER_ALREADY_ACTIVE", "User is already active.", 409)
        target.is_active = True
        self._audit(
            actor,
            "admin.user.reactivate",
            target,
            {"reason": reason, "correlation_id": correlation_id},
        )
        await self.session.commit()
        await self.session.refresh(target)
        return await self._detail(target, BRAND_KEY)

    async def replace_access(
        self,
        actor: User,
        user_id: uuid.UUID,
        data: AdminUserAccessUpdate,
        *,
        correlation_id: str | None = None,
    ) -> EffectiveAccess:
        target = await self._user(user_id)
        await self._require_can_manage(actor, target, data.brand_key)
        if any(item.role == AccessRole.superadmin for item in data.assignments):
            actor_context = await self.access.context(actor, data.brand_key)
            if "*" not in actor_context.permissions:
                raise DomainError(
                    "SUPERADMIN_REQUIRED",
                    "Only a superadmin can grant the superadmin role.",
                    403,
                )
        vendor_ids = {item.vendor_id for item in data.assignments if item.vendor_id}
        if vendor_ids:
            found = set(
                (
                    await self.session.scalars(select(Vendor.id).where(Vendor.id.in_(vendor_ids)))
                ).all()
            )
            if found != vendor_ids:
                raise DomainError(
                    "VENDOR_NOT_FOUND",
                    "Vendor-scoped access references an unknown vendor.",
                    422,
                )
        # The audit row joins the same transaction committed by replace_assignments.
        self._audit(
            actor,
            "admin.user.access.replace",
            target,
            {
                "reason": data.reason,
                "brand_key": data.brand_key,
                "assignments": [
                    item.model_dump(mode="json") for item in data.assignments
                ],
                "correlation_id": correlation_id,
            },
        )
        await self.access.replace_assignments(
            user_id=target.id,
            brand_key=data.brand_key,
            assignments=data.assignments,
        )
        return await self._effective_access(target, data.brand_key)
