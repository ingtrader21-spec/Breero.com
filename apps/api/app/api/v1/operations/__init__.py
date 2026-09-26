"""Operations API resource modules and compatibility exports."""

from app.api.v1.operations.bookings import confirm_booking
from app.api.v1.operations.control_center import (
    capacity_board,
    dispatch_queue,
    exception_queue,
    job_assignment_candidates,
    job_control_detail,
    operations_dashboard,
    operations_integration_failures,
    service_area_operations,
)
from app.api.v1.operations.credentials import upsert_provider_credential
from app.api.v1.operations.dispatch import assign_job, match_job, reassign_job
from app.api.v1.operations.dispatcher import (
    dispatcher_queue,
    update_dispatcher_queue_item,
)
from app.api.v1.operations.router import router
from app.api.v1.operations.workforce import (
    replace_booking_coverage,
    set_vendor_status,
)

__all__ = [
    "router",
    "confirm_booking",
    "upsert_provider_credential",
    "dispatcher_queue",
    "update_dispatcher_queue_item",
    "replace_booking_coverage",
    "match_job",
    "assign_job",
    "reassign_job",
    "set_vendor_status",
    "operations_dashboard",
    "dispatch_queue",
    "exception_queue",
    "capacity_board",
    "service_area_operations",
    "operations_integration_failures",
    "job_control_detail",
    "job_assignment_candidates",
]
