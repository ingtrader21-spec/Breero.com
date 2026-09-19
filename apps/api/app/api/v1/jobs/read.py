import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.jobs.dependencies import ensure_job_access
from app.db.session import get_db
from app.domains.auth.dependencies import require_roles
from app.domains.auth.models import User, UserRole
from app.domains.jobs.models import JobStatus
from app.domains.jobs.repository import JobRepository
from app.domains.jobs.schemas import JobRead

router = APIRouter()


async def list_jobs(
    status: JobStatus | None = None,
    vendor_id: uuid.UUID | None = None,
    worker_id: uuid.UUID | None = None,
    limit: int = Query(100, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(UserRole.operations, UserRole.admin)),
):
    """List jobs; the collection path is registered by the package router."""

    return await JobRepository(session).list(
        status=status,
        vendor_id=vendor_id,
        worker_id=worker_id,
        limit=limit,
    )


@router.get("/{job_id}", response_model=JobRead)
async def get_job(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(
        require_roles(
            UserRole.operations,
            UserRole.admin,
            UserRole.vendor_admin,
            UserRole.technician,
        )
    ),
):
    job = await JobRepository(session).get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    await ensure_job_access(session, user, job)
    return job
