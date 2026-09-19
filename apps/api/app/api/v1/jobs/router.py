from fastapi import APIRouter

from app.api.v1.jobs.read import list_jobs
from app.api.v1.jobs.read import router as read_router
from app.api.v1.jobs.transitions import router as transitions_router
from app.api.v1.jobs.work_requests import router as work_requests_router
from app.domains.jobs.schemas import JobRead

router = APIRouter()
router.add_api_route("", list_jobs, methods=["GET"], response_model=list[JobRead])
router.include_router(read_router)
router.include_router(transitions_router)
router.include_router(work_requests_router)
