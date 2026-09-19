from collections.abc import Mapping
from typing import Any

from celery import Celery
from celery.signals import heartbeat_sent, worker_ready

from app.config import settings
from app.observability import configure_worker_observability, record_worker_heartbeat

configure_worker_observability()


@heartbeat_sent.connect
@worker_ready.connect
def _worker_heartbeat(**_kwargs) -> None:
    record_worker_heartbeat()


EXPECTED_BEAT_TASKS = frozenset(
    {
        "app.workers.tasks.publish_outbox",
        "app.workers.tasks.expire_bookings",
        "app.workers.tasks.release_earnings",
        "app.workers.tasks.generate_weekly_payout_candidates",
    }
)

celery_app = Celery("breero", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    worker_send_task_events=True,
    task_send_sent_event=True,
    timezone="UTC",
    imports=("app.workers.tasks",),
    beat_schedule={
        "publish-outbox": {"task": "app.workers.tasks.publish_outbox", "schedule": 10.0},
        "expire-bookings": {"task": "app.workers.tasks.expire_bookings", "schedule": 60.0},
        "release-earnings": {"task": "app.workers.tasks.release_earnings", "schedule": 3600.0},
        "weekly-payout-candidates": {
            "task": "app.workers.tasks.generate_weekly_payout_candidates",
            "schedule": 604800.0,
        },
    },
)
celery_app.autodiscover_tasks(["app.workers"])


def assert_expected_beat_tasks(app: Celery = celery_app) -> None:
    """Fail startup when a required scheduled task is missing or unregistered."""

    app.loader.import_default_modules()
    app.finalize(auto=True)
    schedule: Mapping[str, Any] = app.conf.beat_schedule or {}
    scheduled = {
        str(entry.get("task"))
        for entry in schedule.values()
        if isinstance(entry, Mapping) and entry.get("task")
    }
    registered = set(app.tasks)
    missing_schedule = sorted(EXPECTED_BEAT_TASKS - scheduled)
    missing_registry = sorted(EXPECTED_BEAT_TASKS - registered)
    if missing_schedule or missing_registry:
        details = []
        if missing_schedule:
            details.append("missing from beat_schedule: " + ", ".join(missing_schedule))
        if missing_registry:
            details.append("not registered: " + ", ".join(missing_registry))
        raise RuntimeError("Celery beat preflight failed; " + "; ".join(details))
