import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.jobs.dependencies import effective_roles
from app.db.session import get_db
from app.domains.auth.dependencies import require_roles
from app.domains.auth.models import AccessRole, User, UserRole
from app.domains.dispatch.control_center import OperationsControlCenterService, QueueFilters
from app.domains.dispatch.operations_schemas import (
    AssignmentCandidates,
    CapacityBoard,
    ExceptionQueue,
    IntegrationFailurePage,
    JobControlDetail,
    OperationsDashboard,
    QueuePage,
    ServiceAreaProjection,
)
from app.domains.dispatch.risk import RiskSeverity
from app.domains.jobs.models import JobStatus

router = APIRouter(prefix="/control-center")

operations_reader = require_roles(UserRole.operations, UserRole.admin)
INTEGRATION_RETRY_ROLES = {AccessRole.finance, AccessRole.admin, AccessRole.superadmin}


@router.get("/summary", response_model=OperationsDashboard)
async def operations_dashboard(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(operations_reader),
) -> OperationsDashboard:
    return await OperationsControlCenterService(session).dashboard()


@router.get("/queue", response_model=QueuePage)
async def dispatch_queue(
    status: list[JobStatus] | None = Query(default=None),
    vendor_id: uuid.UUID | None = None,
    worker_id: uuid.UUID | None = None,
    service_id: uuid.UUID | None = None,
    service_area_id: uuid.UUID | None = None,
    unassigned_only: bool = False,
    at_risk_only: bool = False,
    severity: RiskSeverity | None = None,
    scheduled_from: datetime | None = None,
    scheduled_to: datetime | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=10_000),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(operations_reader),
) -> QueuePage:
    if scheduled_from and scheduled_to and scheduled_to <= scheduled_from:
        raise HTTPException(422, "scheduled_to must be after scheduled_from")
    filters = QueueFilters(
        statuses=tuple(status or ()),
        vendor_id=vendor_id,
        worker_id=worker_id,
        service_id=service_id,
        service_area_id=service_area_id,
        unassigned_only=unassigned_only,
        scheduled_from=scheduled_from,
        scheduled_to=scheduled_to,
        at_risk_only=at_risk_only,
        severity=severity,
    )
    return await OperationsControlCenterService(session).queue(
        filters, limit=limit, offset=offset
    )


@router.get("/exceptions", response_model=ExceptionQueue)
async def exception_queue(
    severity: RiskSeverity | None = None,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(operations_reader),
) -> ExceptionQueue:
    return await OperationsControlCenterService(session).exceptions(severity)


@router.get("/capacity", response_model=CapacityBoard)
async def capacity_board(
    day: date | None = Query(default=None, alias="date"),
    vendor_id: uuid.UUID | None = None,
    include_inactive: bool = False,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(operations_reader),
) -> CapacityBoard:
    return await OperationsControlCenterService(session).capacity(
        day or datetime.now(UTC).date(),
        vendor_id=vendor_id,
        include_inactive=include_inactive,
    )


@router.get("/service-areas", response_model=ServiceAreaProjection)
async def service_area_operations(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(operations_reader),
) -> ServiceAreaProjection:
    return await OperationsControlCenterService(session).service_areas()


@router.get("/integration-failures", response_model=IntegrationFailurePage)
async def operations_integration_failures(
    limit: int = Query(100, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    user: User = Depends(operations_reader),
) -> IntegrationFailurePage:
    roles = await effective_roles(session, user)
    return await OperationsControlCenterService(session).integration_failures(
        limit=limit,
        retry_permitted=bool(roles & INTEGRATION_RETRY_ROLES),
    )


@router.get("/jobs/{job_id}", response_model=JobControlDetail)
async def job_control_detail(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(operations_reader),
) -> JobControlDetail:
    return await OperationsControlCenterService(session).job_detail(job_id)


@router.get("/jobs/{job_id}/candidates", response_model=AssignmentCandidates)
async def job_assignment_candidates(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(operations_reader),
) -> AssignmentCandidates:
    return await OperationsControlCenterService(session).assignment_candidates(job_id)
