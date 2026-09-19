import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.jobs.dependencies import customer_for_user, ensure_job_access, worker_for_user
from app.db.session import get_db
from app.domains.auth.dependencies import require_roles
from app.domains.auth.models import User, UserRole
from app.domains.jobs.repository import JobRepository
from app.domains.jobs.schemas import (
    WorkRequestCreate,
    WorkRequestDecision,
    WorkRequestRead,
)
from app.domains.jobs.service import JobService

router = APIRouter()


@router.post(
    "/{job_id}/work-requests",
    response_model=WorkRequestRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_work_request(
    job_id: uuid.UUID,
    payload: WorkRequestCreate,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.technician)),
):
    worker = await worker_for_user(session, user.id)
    return await JobService(session).create_work_request(job_id, payload, worker.id)


@router.get("/{job_id}/work-requests", response_model=list[WorkRequestRead])
async def list_work_requests(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(
        require_roles(
            UserRole.operations,
            UserRole.admin,
            UserRole.vendor_admin,
            UserRole.technician,
            UserRole.customer,
        )
    ),
):
    job = await JobRepository(session).get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    await ensure_job_access(session, user, job)
    return await JobRepository(session).list_work_requests(job_id)


@router.post("/work-requests/{request_id}/decision", response_model=WorkRequestRead)
async def decide_work_request(
    request_id: uuid.UUID,
    payload: WorkRequestDecision,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.customer)),
):
    customer = await customer_for_user(session, user.id)
    return await JobService(session).decide_work_request(
        request_id,
        payload.approve,
        customer.id,
    )


@router.post("/work-requests/{request_id}/review", response_model=WorkRequestRead)
async def review_work_request(
    request_id: uuid.UUID,
    payload: WorkRequestDecision,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(UserRole.operations, UserRole.admin)),
):
    return await JobService(session).review_work_request(
        request_id,
        payload.approve,
    )
