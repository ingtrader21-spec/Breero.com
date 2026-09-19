import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.access_service import BRAND_KEY, AccessService
from app.domains.auth.models import AccessRole, User
from app.domains.booking.models import Customer
from app.domains.jobs.models import Job
from app.domains.workforce.models import Vendor, Worker


async def worker_for_user(session: AsyncSession, user_id: uuid.UUID) -> Worker:
    worker = await session.scalar(select(Worker).where(Worker.user_id == user_id))
    if not worker:
        raise HTTPException(403, "Account is not linked to a worker")
    return worker


async def customer_for_user(session: AsyncSession, user_id: uuid.UUID) -> Customer:
    customer = await session.scalar(select(Customer).where(Customer.user_id == user_id))
    if not customer:
        raise HTTPException(403, "Account is not linked to a customer")
    return customer


async def vendor_for_user(session: AsyncSession, user_id: uuid.UUID) -> Vendor:
    vendor = await session.scalar(select(Vendor).where(Vendor.owner_user_id == user_id))
    if not vendor:
        raise HTTPException(403, "Account is not linked to a vendor")
    return vendor


PRIVILEGED_JOB_ROLES = {
    AccessRole.operations,
    AccessRole.ops_manager,
    AccessRole.admin,
    AccessRole.superadmin,
}

async def effective_roles(session: AsyncSession, user: User) -> set[AccessRole]:
    context = await AccessService(session).context(user, BRAND_KEY)
    return set(context.roles)

async def _job_visible_to_nonprivileged(
    session: AsyncSession, job, user: User, roles: set[AccessRole]
) -> bool:
    """True if any of the caller's non-privileged roles grants access to this job.

    Checked as a union rather than a first-match chain: a user assigned several
    roles (e.g. customer and technician) must be allowed in when *any* assigned
    role has the required relationship to the job.
    """
    if AccessRole.customer in roles:
        customer = await session.scalar(
            select(Customer).where(Customer.user_id == user.id)
        )
        if customer and job.customer_id == customer.id:
            return True
    if AccessRole.technician in roles:
        worker = await session.scalar(select(Worker).where(Worker.user_id == user.id))
        if worker and job.worker_id == worker.id:
            return True
    if AccessRole.vendor_admin in roles:
        vendor = await session.scalar(
            select(Vendor).where(Vendor.owner_user_id == user.id)
        )
        if vendor and job.vendor_id == vendor.id:
            return True
    return False


async def ensure_job_access(
    session: AsyncSession,
    user: User,
    job: Job,
) -> None:
    roles = await effective_roles(session, user)
    if not roles & PRIVILEGED_JOB_ROLES:
        if not await _job_visible_to_nonprivileged(session, job, user, roles):
            raise HTTPException(403, "Job is not visible to this account")
