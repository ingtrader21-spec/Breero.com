import pytest
from celery import Celery

from app.workers.celery_app import EXPECTED_BEAT_TASKS, assert_expected_beat_tasks, celery_app


def test_production_beat_targets_are_scheduled_and_registered() -> None:
    assert_expected_beat_tasks(celery_app)
    scheduled = {entry["task"] for entry in celery_app.conf.beat_schedule.values()}
    assert EXPECTED_BEAT_TASKS.issubset(scheduled)
    assert EXPECTED_BEAT_TASKS.issubset(celery_app.tasks)


def test_preflight_fails_when_a_required_target_is_missing() -> None:
    broken = Celery("broken", broker="memory://", backend="cache+memory://")
    broken.conf.beat_schedule = {}
    with pytest.raises(RuntimeError, match="missing from beat_schedule"):
        assert_expected_beat_tasks(broken)
