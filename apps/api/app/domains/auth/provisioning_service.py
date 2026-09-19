from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.domains.auth.access_service import AccessService
from app.domains.auth.models import (
    AccessAssignment,
    AccessProfile,
    AccessRole,
    AccountInvitationToken,
    Department,
    TenantScope,
    User,
    UserRole,
)
from app.domains.auth.repository import UserRepository
from app.domains.auth.schemas import (
    InternalAccountRole,
    InternalUserProvisionRequest,
    InternalUserProvisionResponse,
    UserRead,
)
from app.domains.auth.security import hash_password, hash_token, new_opaque_token
from app.domains.common.outbox import AuditLog, EventStatus, IntegrationEvent

ROLE_BINDINGS: dict[
    InternalAccountRole,
    tuple[UserRole, AccessRole, Department, TenantScope],
] = {
    InternalAccountRole.BREERO_SUPPORT: (
        UserRole.finance,
        AccessRole.support,
        Department.customer_support,
        TenantScope.brand,
    ),
    InternalAccountRole.BREERO_DISPATCH: (
        UserRole.operations,
        AccessRole.operations,
        Department.dispatch,
        TenantScope.brand,
    ),
    InternalAccountRole.BREERO_ADMIN: (
        UserRole.admin,
        AccessRole.admin,
        Department.administration,
        TenantScope.global_,
    ),
}


class InternalUserProvisioningService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.users = UserRepository(session)

    async def provision(
        self,
        *,
        actor: User,
        data: InternalUserProvisionRequest,
    ) -> InternalUserProvisionResponse:
        email = str(data.email).strip().lower()
        if await self.users.by_email(email):
            raise HTTPException(409, "Email already registered")

        legacy_role, access_role, department, tenant_scope = ROLE_BINDINGS[data.role]
        invitation_state: Literal[
            "not_required",
            "pending_configuration",
            "pending_delivery",
        ] = "not_required"
        try:
            user = await self.users.add(
                User(
                    email=email,
                    full_name=data.full_name.strip(),
                    password_hash=await hash_password(new_opaque_token()),
                    role=legacy_role,
                    is_active=True,
                    email_verified=settings.keycloak_enabled,
                )
            )
            self.session.add(
                AccessProfile(
                    user_id=user.id,
                    brand_key=data.brand_key,
                )
            )
            self.session.add(
                AccessAssignment(
                    user_id=user.id,
                    brand_key=data.brand_key,
                    role_key=access_role.value,
                    department=department.value,
                    tenant_scope=tenant_scope.value,
                    vendor_id=None,
                    active=True,
                    is_primary=True,
                )
            )

            if not settings.keycloak_enabled:
                raw_invitation = new_opaque_token()
                self.session.add(
                    AccountInvitationToken(
                        user_id=user.id,
                        token_hash=hash_token(raw_invitation),
                        expires_at=datetime.now(UTC) + timedelta(hours=24),
                        created_by=actor.id,
                    )
                )
                deliverable = (
                    settings.email_enabled
                    and settings.live_email_delivery
                    and settings.transactional_email_mode != "disabled"
                )
                invitation_state = (
                    "pending_delivery"
                    if deliverable
                    else "pending_configuration"
                )
                self.session.add(
                    IntegrationEvent(
                        aggregate_type="user",
                        aggregate_id=user.id,
                        event_type="internal_user_invitation_requested",
                        idempotency_key=f"internal-user-invitation:{user.id}",
                        payload={
                            "user_id": str(user.id),
                            "email": user.email,
                            "role": data.role.value,
                            "token": raw_invitation,
                        },
                        status=(
                            EventStatus.PENDING
                            if deliverable
                            else EventStatus.PENDING_CONFIGURATION
                        ),
                        attempts=0,
                        available_at=datetime.now(UTC),
                    )
                )

            self.session.add(
                AuditLog(
                    actor_id=actor.id,
                    actor_type="admin",
                    action="admin.user.provision",
                    resource_type="user",
                    resource_id=user.id,
                    metadata_json={
                        "role": data.role.value,
                        "brand_key": data.brand_key,
                        "identity_mode": (
                            "keycloak"
                            if settings.keycloak_enabled
                            else "invitation"
                        ),
                    },
                    created_at=datetime.now(UTC),
                )
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(409, "Email already registered") from exc

        await self.session.refresh(user)
        return InternalUserProvisionResponse(
            user=UserRead.model_validate(user),
            access=await AccessService(self.session).context(
                user,
                data.brand_key,
            ),
            credential_mode=(
                "keycloak"
                if settings.keycloak_enabled
                else "invitation"
            ),
            invitation_state=invitation_state,
        )
