"""Admin user lifecycle read models and commands.

These schemas describe Breero-owned application state only. When Keycloak is the
identity authority, credentials, MFA and the upstream account status stay in
Keycloak; Breero only controls whether a linked account may use Breero portals.
"""

import enum
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.domains.auth.models import AccessRole, UserRole
from app.domains.auth.schemas import AccessProfileUpdate, PortalContext


class AdminUserStatus(enum.StrEnum):
    active = "active"
    disabled = "disabled"


class AdminUserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    status: AdminUserStatus
    email_verified: bool
    identity_linked: bool
    created_at: datetime
    updated_at: datetime


class AdminUserList(BaseModel):
    items: list[AdminUserSummary]
    total: int
    page: int
    page_size: int


class IdentityLinkSummary(BaseModel):
    """Issuer metadata only; the upstream subject identifier is never exposed."""

    issuer: str
    linked_at: datetime
    last_seen_at: datetime | None


class AdminUserDetail(AdminUserSummary):
    identity_authority: Literal["keycloak", "local"]
    identity_links: list[IdentityLinkSummary]
    active_session_count: int
    access: PortalContext


class PermissionOverride(BaseModel):
    permission: str
    allow: bool
    source: Literal["role", "user"]
    role: AccessRole | None = None


class EffectiveAccess(BaseModel):
    user_id: uuid.UUID
    brand_key: str
    status: AdminUserStatus
    identity_authority: Literal["keycloak", "local"]
    managed_profile: bool
    access: PortalContext
    overrides: list[PermissionOverride]
    # A disabled account keeps its assignments for reactivation but has no
    # effective permissions while disabled.
    effective_permissions: list[str]


class AdminUserLifecycleCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=500)


class AdminUserAccessUpdate(AccessProfileUpdate):
    """Access replacement with the shared primary/duplicate validation plus a reason."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=500)
