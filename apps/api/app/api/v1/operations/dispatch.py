import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.domains.auth.dependencies import require_roles
from app.domains.auth.models import User, UserRole
from app.domains.dispatch.schemas import (
    AssignmentRead,
    ManualAssignment,
    OfferRead,
    Reassignment,
    ReassignmentRead,
)
from app.domains.dispatch.service import DispatchService

router = APIRouter()


@router.post("/jobs/{job_id}/match", response_model=list[OfferRead])
async def match_job(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.operations, UserRole.admin)),
):
    return await DispatchService(session).match(job_id, user.id)


@router.post(
    "/jobs/{job_id}/assign",
    response_model=AssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def assign_job(
    job_id: uuid.UUID,
    payload: ManualAssignment,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.operations, UserRole.admin)),
):
    return await DispatchService(session).manual_assign(
        job_id,
        payload.vendor_id,
        payload.worker_id,
        user.id,
        payload.reason,
    )


@router.post("/jobs/{job_id}/reassign", response_model=ReassignmentRead)
async def reassign_job(
    job_id: uuid.UUID,
    payload: Reassignment,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.operations, UserRole.admin)),
) -> ReassignmentRead:
    assignment, released, job = await DispatchService(session).reassign(
        job_id,
        payload.vendor_id,
        payload.worker_id,
        user.id,
        payload.reason,
        payload.expected_version,
    )
    return ReassignmentRead(
        assignment=AssignmentRead.model_validate(assignment),
        released_assignment_id=released.id,
        job_id=job.id,
        job_status=job.status,
        job_version=job.version,
    )
