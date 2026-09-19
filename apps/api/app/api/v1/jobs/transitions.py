import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.jobs.dependencies import worker_for_user
from app.db.session import get_db
from app.domains.auth.dependencies import require_roles
from app.domains.auth.models import User, UserRole
from app.domains.jobs.models import JobStatus
from app.domains.jobs.repository import JobRepository
from app.domains.jobs.schemas import JobRead, TechnicianNoteRequest, TransitionRequest
from app.domains.jobs.service import JobService

router = APIRouter()


@router.post("/{job_id}/transition", response_model=JobRead)
async def transition_job(
    job_id: uuid.UUID,
    payload: TransitionRequest,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.operations, UserRole.admin)),
):
    return await JobService(session).transition(
        job_id,
        payload.status,
        user.id,
        user.role.value,
        payload.reason,
    )


@router.post("/{job_id}/technician/{command}", response_model=JobRead)
async def technician_command(
    job_id: uuid.UUID,
    command: str,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.technician)),
):
    worker = await worker_for_user(session, user.id)
    job = await JobRepository(session).get(job_id)
    if not job or job.worker_id != worker.id:
        raise HTTPException(403, "Technician is not assigned to this job")

    targets = {
        "en-route": JobStatus.EN_ROUTE,
        "arrive": JobStatus.ON_SITE,
        "diagnose": JobStatus.DIAGNOSING,
        "start": JobStatus.IN_PROGRESS,
    }
    if command not in targets:
        raise HTTPException(422, "Unknown technician command")
    return await JobService(session).transition(
        job_id,
        targets[command],
        user.id,
        "worker",
    )


@router.post("/{job_id}/diagnostic", response_model=JobRead)
async def record_diagnostic(
    job_id: uuid.UUID,
    payload: TechnicianNoteRequest,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.technician)),
):
    worker = await worker_for_user(session, user.id)
    return await JobService(session).technician_note_transition(
        job_id,
        worker.id,
        user.id,
        "diagnostic_notes",
        payload.notes,
        JobStatus.DIAGNOSING,
    )


@router.post("/{job_id}/completion", response_model=JobRead)
async def complete_with_notes(
    job_id: uuid.UUID,
    payload: TechnicianNoteRequest,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.technician)),
):
    worker = await worker_for_user(session, user.id)
    return await JobService(session).technician_note_transition(
        job_id,
        worker.id,
        user.id,
        "completion_notes",
        payload.notes,
        JobStatus.COMPLETED,
    )
