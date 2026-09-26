"""Resolve the provider organization from the authenticated principal.

Provider self-service operations must never trust a caller-supplied vendor identifier.
The vendor is derived from the principal's active vendor-scoped access assignment
(falling back to legacy ownership), and every child record is re-checked against it.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.domains.auth.models import User
from app.domains.provider_catalog.repository import ProviderCatalogRepository

from .models import Vendor, VendorStatus, Worker

LOCKED_VENDOR_STATUSES = frozenset({VendorStatus.SUSPENDED, VendorStatus.REJECTED})


async def provider_vendor(
    session: AsyncSession,
    user: User,
    *,
    lock: bool = False,
    write: bool = False,
) -> Vendor:
    vendor = await ProviderCatalogRepository(session).vendor_for_user(user, lock=lock)
    if not vendor:
        raise DomainError(
            "PROVIDER_SCOPE_REQUIRED",
            "Account is not linked to a provider organization.",
            403,
        )
    if write and vendor.status in LOCKED_VENDOR_STATUSES:
        raise DomainError(
            "PROVIDER_NOT_EDITABLE",
            "Provider organization cannot be changed in its current state.",
            409,
        )
    return vendor


async def provider_worker(
    session: AsyncSession,
    vendor: Vendor,
    worker_id: uuid.UUID,
    *,
    lock: bool = False,
) -> Worker:
    query = select(Worker).where(Worker.id == worker_id, Worker.vendor_id == vendor.id)
    if lock:
        query = query.with_for_update()
    worker = await session.scalar(query)
    if not worker:
        # 404 rather than 403: another provider's worker must be indistinguishable
        # from a worker that does not exist.
        raise DomainError("WORKER_NOT_FOUND", "Provider professional not found.", 404)
    return worker
