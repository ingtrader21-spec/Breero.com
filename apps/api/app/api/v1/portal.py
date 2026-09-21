from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.domains.auth.dependencies import current_user, require_permissions
from app.domains.auth.models import User
from app.domains.finance.models import EarningStatus, PayoutStatus
from app.domains.jobs.models import JobStatus
from app.domains.portal.schemas import (
    AdminOverview,
    AuditEventList,
    EffectiveCapabilities,
    OperationsOverview,
    ProviderCredentialList,
    ProviderEarningList,
    ProviderJobList,
    ProviderOverview,
    ProviderPayoutBatchList,
    ProviderWorkerList,
)
from app.domains.portal.service import PortalReadService

router = APIRouter()


@router.get("/capabilities", response_model=EffectiveCapabilities)
async def portal_capabilities(
    _: User = Depends(current_user),
) -> EffectiveCapabilities:
    return PortalReadService.capabilities()


@router.get("/provider/overview", response_model=ProviderOverview)
async def provider_overview(
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_permissions("provider.profile.read")),
) -> ProviderOverview:
    return await PortalReadService(session).provider_overview(user)


@router.get("/provider/jobs", response_model=ProviderJobList)
async def provider_jobs(
    status: JobStatus | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_permissions("provider.jobs.read")),
) -> ProviderJobList:
    return await PortalReadService(session).provider_jobs(user, status, limit, offset)


@router.get("/provider/workers", response_model=ProviderWorkerList)
async def provider_workers(
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_permissions("provider.workers.read")),
) -> ProviderWorkerList:
    return await PortalReadService(session).provider_workers(user, limit, offset)


@router.get("/provider/credentials", response_model=ProviderCredentialList)
async def provider_credentials(
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_permissions("provider.credentials.read")),
) -> ProviderCredentialList:
    return await PortalReadService(session).provider_credentials(user, limit, offset)


@router.get("/provider/earnings", response_model=ProviderEarningList)
async def provider_earnings(
    status: EarningStatus | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_permissions("provider.earnings.read")),
) -> ProviderEarningList:
    return await PortalReadService(session).provider_earnings(user, status, limit, offset)


@router.get("/provider/payout-batches", response_model=ProviderPayoutBatchList)
async def provider_payout_batches(
    status: PayoutStatus | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_permissions("provider.payouts.read")),
) -> ProviderPayoutBatchList:
    return await PortalReadService(session).provider_payout_batches(
        user,
        status,
        limit,
        offset,
    )


@router.get("/operations/overview", response_model=OperationsOverview)
async def operations_overview(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permissions("ops.dispatch.read")),
) -> OperationsOverview:
    return await PortalReadService(session).operations_overview()


@router.get(
    "/admin/overview",
    response_model=AdminOverview,
    responses={403: {"description": "Insufficient permissions for the complete admin overview."}},
)
async def admin_overview(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(
        require_permissions(
            "admin.capabilities.read",
            "admin.audit.read",
            "admin.access.manage",
            "admin.integrations.read",
            "ops.dispatch.read",
            "ops.bookings.read",
            "ops.providers.read",
            "ops.customers.read",
            "finance.ledger.read",
            "finance.payouts.read",
        )
    ),
) -> AdminOverview:
    """Require access to every section before reading the cross-domain overview."""
    return await PortalReadService(session).admin_overview()


@router.get("/admin/audit", response_model=AuditEventList)
async def admin_audit(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permissions("admin.audit.read")),
) -> AuditEventList:
    return await PortalReadService(session).audit_events(limit, offset)
