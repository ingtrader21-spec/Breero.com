"""Job and work-request API resources with compatibility exports."""

from app.api.v1.jobs.dependencies import (
    customer_for_user,
    ensure_job_access,
    vendor_for_user,
    worker_for_user,
)
from app.api.v1.jobs.read import get_job, list_jobs
from app.api.v1.jobs.router import router
from app.api.v1.jobs.transitions import (
    complete_with_notes,
    record_diagnostic,
    technician_command,
    transition_job,
)
from app.api.v1.jobs.work_requests import (
    create_work_request,
    decide_work_request,
    list_work_requests,
    review_work_request,
)

__all__ = [
    "router",
    "worker_for_user",
    "customer_for_user",
    "vendor_for_user",
    "ensure_job_access",
    "list_jobs",
    "get_job",
    "transition_job",
    "technician_command",
    "record_diagnostic",
    "complete_with_notes",
    "create_work_request",
    "list_work_requests",
    "decide_work_request",
    "review_work_request",
]
