import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.domains.auth.dependencies import require_permissions, require_roles
from app.domains.auth.models import User, UserRole
from app.domains.finance.models import EarningStatus, PayoutStatus
from app.domains.finance.read_models import (
    EarningPage,
    EarningsSummary,
    FinanceExceptionList,
    FinanceStatus,
    PaymentPage,
    PayoutBatchDetail,
    PayoutBatchPage,
    PayoutCandidates,
    PayoutHistoryEntry,
    ProviderFinanceSummary,
    ProviderPayoutDetail,
    ProviderPayoutPage,
    RefundPage,
)
from app.domains.finance.read_service import (
    FinanceReadService,
    ProviderFinanceService,
    finance_status,
)
from app.domains.finance.repository import FinanceRepository
from app.domains.finance.schemas import (
    CompensationPlanCreate,
    CompensationPlanRead,
    EarningAdjustmentCreate,
    EarningRead,
    PayoutBatchCreate,
    PayoutBatchRead,
)
from app.domains.finance.service import FinanceService
from app.domains.payments.models import PaymentStatus, RefundStatus

# Commands: mounted only while PAYOUT_ENABLED is true (see api/v1/router.py).
router = APIRouter()
# Read-only projections of persisted finance state: mounted unconditionally.
read_router = APIRouter()
# Provider-scoped reads: the vendor is always the authenticated provider's own.
provider_router = APIRouter()

finance_staff = require_roles(UserRole.finance, UserRole.admin)
provider_finance = require_permissions("provider.finance.read")
Currency = Annotated[str, Query(pattern=r"^[A-Z]{3}$")]


@router.post("/compensation-plans", response_model=CompensationPlanRead, status_code=201)
async def create_compensation_plan(
    payload: CompensationPlanCreate,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(finance_staff),
):
    return await FinanceService(session).create_compensation_plan(payload, user.id)


@router.post("/earnings/{earning_id}/adjustments", status_code=201)
async def adjust_earning(
    earning_id: uuid.UUID,
    payload: EarningAdjustmentCreate,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(finance_staff),
):
    return await FinanceService(session).adjust_earning(
        earning_id, payload.amount_minor, payload.adjustment_type, payload.reason,
        payload.idempotency_key, user.id,
    )


@router.post("/payout-batches", response_model=PayoutBatchRead, status_code=201)
async def create_batch(
    payload: PayoutBatchCreate,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(finance_staff),
):
    return await FinanceService(session).create_batch(payload.currency, payload.vendor_id, _.id)


@router.post("/payout-batches/{batch_id}/approve", response_model=PayoutBatchRead)
async def approve_batch(
    batch_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(finance_staff),
):
    return await FinanceService(session).approve_batch(batch_id, user.id)


@router.post("/payout-batches/{batch_id}/submit", response_model=PayoutBatchRead)
async def submit_batch(
    batch_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(finance_staff),
):
    return await FinanceService(session).submit_batch(batch_id, user.id)


@read_router.get("/status", response_model=FinanceStatus)
async def get_finance_status(_: Annotated[User, Depends(finance_staff)]) -> FinanceStatus:
    return finance_status()


@read_router.get("/earnings", response_model=list[EarningRead])
async def list_earnings(
    vendor_id: uuid.UUID | None = None,
    status: EarningStatus | None = None,
    limit: int = Query(200, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(finance_staff),
):
    return await FinanceRepository(session).list_earnings(vendor_id, status, limit)


@read_router.get("/earnings/summary", response_model=EarningsSummary)
async def get_earnings_summary(
    _: Annotated[User, Depends(finance_staff)],
    session: Annotated[AsyncSession, Depends(get_db)],
    vendor_id: uuid.UUID | None = None,
) -> EarningsSummary:
    return await FinanceReadService(session).earnings_summary(vendor_id)


@read_router.get("/exceptions", response_model=FinanceExceptionList)
async def list_finance_exceptions(
    _: Annotated[User, Depends(finance_staff)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> FinanceExceptionList:
    return await FinanceReadService(session).exceptions()


@read_router.get("/payout-candidates", response_model=PayoutCandidates)
async def get_payout_candidates(
    _: Annotated[User, Depends(finance_staff)],
    session: Annotated[AsyncSession, Depends(get_db)],
    currency: Currency = "USD",
    vendor_id: uuid.UUID | None = None,
) -> PayoutCandidates:
    return await FinanceReadService(session).payout_candidates(currency, vendor_id)


@read_router.get("/payout-batches", response_model=PayoutBatchPage)
async def list_payout_batches(
    _: Annotated[User, Depends(finance_staff)],
    session: Annotated[AsyncSession, Depends(get_db)],
    batch_status: PayoutStatus | None = Query(default=None, alias="status"),
    currency: Annotated[str | None, Query(pattern=r"^[A-Z]{3}$")] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> PayoutBatchPage:
    return await FinanceReadService(session).payout_batches(
        status=batch_status, currency=currency, page=page, page_size=page_size
    )


@read_router.get("/payout-batches/{batch_id}", response_model=PayoutBatchDetail)
async def get_payout_batch(
    batch_id: uuid.UUID,
    user: Annotated[User, Depends(finance_staff)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PayoutBatchDetail:
    return await FinanceReadService(session).payout_batch(batch_id, user.id)


@read_router.get("/payout-batches/{batch_id}/history", response_model=list[PayoutHistoryEntry])
async def get_payout_batch_history(
    batch_id: uuid.UUID,
    _: Annotated[User, Depends(finance_staff)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[PayoutHistoryEntry]:
    return await FinanceReadService(session).payout_history(batch_id)


@read_router.get("/payments", response_model=PaymentPage)
async def list_payments(
    _: Annotated[User, Depends(finance_staff)],
    session: Annotated[AsyncSession, Depends(get_db)],
    payment_status: PaymentStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> PaymentPage:
    return await FinanceReadService(session).payments(
        status=payment_status, page=page, page_size=page_size
    )


@read_router.get("/refunds", response_model=RefundPage)
async def list_refunds(
    _: Annotated[User, Depends(finance_staff)],
    session: Annotated[AsyncSession, Depends(get_db)],
    refund_status: RefundStatus | None = Query(default=None, alias="status"),
    payment_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> RefundPage:
    return await FinanceReadService(session).refunds(
        status=refund_status, payment_id=payment_id, page=page, page_size=page_size
    )


@provider_router.get("/summary", response_model=ProviderFinanceSummary)
async def get_provider_finance_summary(
    user: Annotated[User, Depends(provider_finance)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProviderFinanceSummary:
    return await ProviderFinanceService(session).summary(user)


@provider_router.get("/earnings", response_model=EarningPage)
async def list_provider_earnings(
    user: Annotated[User, Depends(provider_finance)],
    session: Annotated[AsyncSession, Depends(get_db)],
    earning_status: EarningStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> EarningPage:
    return await ProviderFinanceService(session).earnings(
        user, status=earning_status, page=page, page_size=page_size
    )


@provider_router.get("/payouts", response_model=ProviderPayoutPage)
async def list_provider_payouts(
    user: Annotated[User, Depends(provider_finance)],
    session: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> ProviderPayoutPage:
    return await ProviderFinanceService(session).payouts(user, page=page, page_size=page_size)


@provider_router.get("/payouts/{payout_id}", response_model=ProviderPayoutDetail)
async def get_provider_payout(
    payout_id: uuid.UUID,
    user: Annotated[User, Depends(provider_finance)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProviderPayoutDetail:
    return await ProviderFinanceService(session).payout(user, payout_id)
