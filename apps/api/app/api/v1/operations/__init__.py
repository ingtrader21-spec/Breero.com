"""Operations API resource modules and compatibility exports."""

from app.api.v1.operations.bookings import confirm_booking
from app.api.v1.operations.credentials import upsert_provider_credential
from app.api.v1.operations.dispatch import assign_job, match_job
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
    "set_vendor_status",
]
