"""Server-owned job lifecycle vocabulary shared by routers and read models.

Operations screens render these values; they never re-derive them in the browser.
"""

from .models import JobStatus
from .service import TRANSITIONS

TERMINAL_JOB_STATUSES = frozenset({JobStatus.COMPLETED, JobStatus.CANCELLED})
ACTIVE_JOB_STATUSES = frozenset(set(JobStatus) - TERMINAL_JOB_STATUSES)
UNASSIGNED_JOB_STATUSES = frozenset({JobStatus.CREATED, JobStatus.MATCHING, JobStatus.OFFERED})
FIELD_EXECUTION_STATUSES = frozenset(
    {
        JobStatus.EN_ROUTE,
        JobStatus.ON_SITE,
        JobStatus.DIAGNOSING,
        JobStatus.IN_PROGRESS,
    }
)
ASSIGNED_WORK_STATUSES = frozenset(
    {JobStatus.ASSIGNED, JobStatus.AWAITING_APPROVAL} | FIELD_EXECUTION_STATUSES
)

# Entering these states has side effects (offers, assignments, booking slot) that only
# the dispatch commands perform, so the generic operator transition must not set them.
DISPATCH_OWNED_TARGETS = frozenset({JobStatus.MATCHING, JobStatus.OFFERED, JobStatus.ASSIGNED})

TECHNICIAN_COMMANDS: dict[str, JobStatus] = {
    "en-route": JobStatus.EN_ROUTE,
    "arrive": JobStatus.ON_SITE,
    "diagnose": JobStatus.DIAGNOSING,
    "start": JobStatus.IN_PROGRESS,
}

_STATUS_ORDER = {status: index for index, status in enumerate(JobStatus)}


def allowed_transitions(status: JobStatus) -> list[JobStatus]:
    """Targets the authoritative state machine accepts from ``status``."""
    return sorted(TRANSITIONS[status], key=_STATUS_ORDER.__getitem__)


def operator_transitions(status: JobStatus) -> list[JobStatus]:
    """Targets an operator may set directly through the generic transition command."""
    return [target for target in allowed_transitions(status) if target not in DISPATCH_OWNED_TARGETS]


def technician_commands(status: JobStatus) -> list[str]:
    """Technician field commands that are currently legal for ``status``."""
    return [
        command
        for command, target in TECHNICIAN_COMMANDS.items()
        if target in TRANSITIONS[status]
    ]
