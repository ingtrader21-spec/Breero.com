"""Tenant scope resolution for analytics reads.

Scope is resolved fail-closed from the caller's effective access context:

* marketplace scope requires ``analytics.marketplace.read`` held through an
  internal (non customer/provider) global or brand assignment, and no
  vendor-scoped assignment at all, so a provider member can never widen their
  view to the whole marketplace;
* provider scope requires ``analytics.provider.read`` and a provider
  organization membership, and is always limited to that one vendor.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.domains.analytics.schemas import AnalyticsScopeKind
from app.domains.auth.access_service import BRAND_KEY, AccessService
from app.domains.auth.models import AccessAssignment, AccessRole, TenantScope, User
from app.domains.auth.schemas import PortalContext
from app.domains.workforce.models import Vendor

MARKETPLACE_PERMISSION = "analytics.marketplace.read"
PROVIDER_PERMISSION = "analytics.provider.read"
EXTERNAL_ROLES = frozenset({AccessRole.customer, AccessRole.vendor_admin, AccessRole.technician})


@dataclass(frozen=True, slots=True)
class AnalyticsScope:
    kind: AnalyticsScopeKind
    vendor_id: uuid.UUID | None = None


def _has(context: PortalContext, permission: str) -> bool:
    return "*" in context.permissions or permission in context.permissions


def marketplace_scope_from_context(context: PortalContext) -> AnalyticsScope:
    if not _has(context, MARKETPLACE_PERMISSION):
        raise DomainError("ANALYTICS_FORBIDDEN", "Marketplace analytics permission is required.", 403)
    if any(item.tenant_scope == TenantScope.vendor for item in context.assignments):
        raise DomainError(
            "ANALYTICS_SCOPE_DENIED",
            "Provider-scoped accounts cannot read marketplace-wide analytics.",
            403,
        )
    if not any(
        item.tenant_scope in {TenantScope.global_, TenantScope.brand}
        and item.role not in EXTERNAL_ROLES
        for item in context.assignments
    ):
        raise DomainError(
            "ANALYTICS_SCOPE_DENIED",
            "An internal marketplace assignment is required for marketplace analytics.",
            403,
        )
    return AnalyticsScope(AnalyticsScopeKind.marketplace)


async def _provider_vendor_id(session: AsyncSession, user: User) -> uuid.UUID | None:
    vendor_id = await session.scalar(
        select(AccessAssignment.vendor_id)
        .where(
            AccessAssignment.user_id == user.id,
            AccessAssignment.brand_key == BRAND_KEY,
            AccessAssignment.tenant_scope == TenantScope.vendor.value,
            AccessAssignment.vendor_id.is_not(None),
            AccessAssignment.active.is_(True),
        )
        .order_by(AccessAssignment.is_primary.desc(), AccessAssignment.created_at)
        .limit(1)
    )
    if vendor_id is not None:
        return vendor_id
    return await session.scalar(select(Vendor.id).where(Vendor.owner_user_id == user.id))


async def resolve_marketplace_scope(session: AsyncSession, user: User) -> AnalyticsScope:
    context = await AccessService(session).context(user, BRAND_KEY)
    return marketplace_scope_from_context(context)


async def resolve_provider_scope(session: AsyncSession, user: User) -> AnalyticsScope:
    context = await AccessService(session).context(user, BRAND_KEY)
    if not _has(context, PROVIDER_PERMISSION):
        raise DomainError("ANALYTICS_FORBIDDEN", "Provider analytics permission is required.", 403)
    vendor_id = await _provider_vendor_id(session, user)
    if vendor_id is None:
        raise DomainError(
            "PROVIDER_SCOPE_REQUIRED",
            "Account is not linked to a provider organization.",
            403,
        )
    return AnalyticsScope(AnalyticsScopeKind.provider, vendor_id)
