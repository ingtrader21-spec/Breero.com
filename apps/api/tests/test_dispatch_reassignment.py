import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.domains.booking.models import Booking
from app.domains.common.outbox import AuditLog
from app.domains.dispatch import service as dispatch_service
from app.domains.dispatch.models import Assignment, AssignmentStatus
from app.domains.dispatch.service import DispatchService, reserved_slot_conflict
from app.domains.jobs.models import Job, JobStatus


def make_job(**overrides) -> Job:
    values = dict(
        id=uuid.uuid4(),
        booking_id=uuid.uuid4(),
        service_id=uuid.uuid4(),
        address_id=uuid.uuid4(),
        vendor_id=uuid.uuid4(),
        worker_id=uuid.uuid4(),
        status=JobStatus.ASSIGNED,
        scheduled_start=datetime.now(UTC) + timedelta(days=1),
        scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=2),
        version=3,
    )
    values.update(overrides)
    return Job(**values)


class Harness:
    """DispatchService over a recording session; persistence is mocked."""

    def __init__(self, job: Job | None, booking: Booking | None = None) -> None:
        self.calls: list[str] = []
        self.added: list[object] = []
        self.events: list[object] = []
        self.session = MagicMock()
        self.session.get = AsyncMock(return_value=booking)
        self.session.add = MagicMock(side_effect=self._add)
        self.session.flush = AsyncMock(side_effect=lambda: self.calls.append("flush"))
        self.session.commit = AsyncMock(side_effect=lambda: self.calls.append("commit"))
        self.session.rollback = AsyncMock()
        self.session.refresh = AsyncMock()
        self.service = DispatchService(self.session)
        self.service.jobs = MagicMock()
        self.service.jobs.get = AsyncMock(return_value=job)
        self.service.jobs.add_event = MagicMock(side_effect=self.events.append)
        self.current = (
            Assignment(
                id=uuid.uuid4(),
                job_id=job.id,
                vendor_id=job.vendor_id,
                worker_id=job.worker_id,
                status=AssignmentStatus.ACTIVE,
            )
            if job is not None and job.worker_id is not None
            else None
        )
        self.service.repo = MagicMock()
        self.service.repo.active_assignment = AsyncMock(return_value=self.current)
        self.service.repo.dispatchable_worker = AsyncMock(
            return_value=SimpleNamespace(id=uuid.uuid4())
        )

    def _add(self, value: object) -> None:
        self.calls.append(f"add:{type(value).__name__}")
        self.added.append(value)


def test_reserved_slot_conflict_only_applies_to_booking_backed_jobs() -> None:
    worker_id = uuid.uuid4()
    assert reserved_slot_conflict(None, worker_id) is False
    assert reserved_slot_conflict(Booking(provider_worker_id=worker_id), worker_id) is False
    assert reserved_slot_conflict(Booking(provider_worker_id=uuid.uuid4()), worker_id) is True
    assert reserved_slot_conflict(Booking(provider_worker_id=None), worker_id) is True


@pytest.mark.asyncio
async def test_match_sends_one_offer_per_vendor_per_round() -> None:
    # dispatch_offers is UNIQUE(job_id, vendor_id, round): a vendor with several
    # dispatchable workers must receive exactly one offer per round.
    job = make_job(status=JobStatus.CREATED, vendor_id=None, worker_id=None)
    harness = Harness(job)
    vendor_a, vendor_b = SimpleNamespace(id=uuid.uuid4()), SimpleNamespace(id=uuid.uuid4())
    workers = [SimpleNamespace(id=uuid.uuid4()) for _ in range(3)]
    harness.service.repo.offers_for_job = AsyncMock(return_value=[])
    harness.service.repo.candidate_workers = AsyncMock(
        return_value=[(vendor_a, workers[0]), (vendor_a, workers[1]), (vendor_b, workers[2])]
    )
    harness.service.job_service = MagicMock()

    offers = await harness.service.match(job.id, uuid.uuid4())

    assert [(offer.vendor_id, offer.worker_id) for offer in offers] == [
        (vendor_a.id, workers[0].id),
        (vendor_b.id, workers[2].id),
    ]
    assert [offer.score for offer in offers] == [1000, 999]
    assert {offer.round for offer in offers} == {1}
    assert harness.calls[-1] == "commit"


@pytest.mark.asyncio
async def test_reassign_unknown_job_is_not_found() -> None:
    harness = Harness(None)
    with pytest.raises(HTTPException) as raised:
        await harness.service.reassign(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "r")
    assert raised.value.status_code == 404


@pytest.mark.asyncio
async def test_reassign_rejects_stale_version() -> None:
    job = make_job()
    harness = Harness(job)
    with pytest.raises(HTTPException) as raised:
        await harness.service.reassign(
            job.id, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "r", expected_version=2
        )
    assert raised.value.status_code == 409
    assert "changed" in raised.value.detail
    harness.session.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [JobStatus.CREATED, JobStatus.OFFERED, JobStatus.EN_ROUTE, JobStatus.IN_PROGRESS, JobStatus.COMPLETED],
)
async def test_reassign_only_allowed_before_travel(status: JobStatus) -> None:
    job = make_job(status=status)
    harness = Harness(job)
    with pytest.raises(HTTPException) as raised:
        await harness.service.reassign(job.id, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "r")
    assert raised.value.status_code == 409
    harness.session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_reassign_requires_an_active_assignment() -> None:
    job = make_job()
    harness = Harness(job)
    harness.service.repo.active_assignment = AsyncMock(return_value=None)
    with pytest.raises(HTTPException) as raised:
        await harness.service.reassign(job.id, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "r")
    assert raised.value.status_code == 409


@pytest.mark.asyncio
async def test_reassign_to_same_worker_is_rejected() -> None:
    job = make_job()
    harness = Harness(job)
    with pytest.raises(HTTPException) as raised:
        await harness.service.reassign(job.id, job.vendor_id, job.worker_id, uuid.uuid4(), "r")
    assert raised.value.status_code == 409


@pytest.mark.asyncio
async def test_reassign_without_booking_requires_dispatchable_worker() -> None:
    job = make_job()
    harness = Harness(job)
    harness.service.repo.dispatchable_worker = AsyncMock(return_value=None)
    with pytest.raises(HTTPException) as raised:
        await harness.service.reassign(job.id, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "r")
    assert raised.value.status_code == 409
    assert harness.current is not None and harness.current.status == AssignmentStatus.ACTIVE


@pytest.mark.asyncio
async def test_booking_backed_reassign_rejects_vendor_mismatch(monkeypatch) -> None:
    job = make_job()
    booking = Booking(id=job.booking_id, provider_worker_id=job.worker_id)
    harness = Harness(job, booking)
    new_worker = SimpleNamespace(id=uuid.uuid4())

    async def qualified(_self, _booking, _worker_id):
        return new_worker, SimpleNamespace(id=uuid.uuid4())

    monkeypatch.setattr(dispatch_service.OperatorSchedulingService, "_qualified_worker", qualified)
    with pytest.raises(HTTPException) as raised:
        await harness.service.reassign(job.id, uuid.uuid4(), new_worker.id, uuid.uuid4(), "r")
    assert raised.value.status_code == 409
    assert booking.provider_worker_id == job.worker_id


@pytest.mark.asyncio
async def test_booking_backed_reassign_moves_slot_releases_and_records(monkeypatch) -> None:
    previous_worker, previous_vendor = uuid.uuid4(), uuid.uuid4()
    job = make_job(worker_id=previous_worker, vendor_id=previous_vendor)
    booking = Booking(id=job.booking_id, provider_worker_id=previous_worker)
    harness = Harness(job, booking)
    new_vendor = SimpleNamespace(id=uuid.uuid4())
    new_worker = SimpleNamespace(id=uuid.uuid4())
    qualified_calls: list[tuple[object, object]] = []

    async def qualified(_self, checked_booking, worker_id):
        qualified_calls.append((checked_booking, worker_id))
        return new_worker, new_vendor

    monkeypatch.setattr(dispatch_service.OperatorSchedulingService, "_qualified_worker", qualified)
    actor = uuid.uuid4()

    replacement, released, result = await harness.service.reassign(
        job.id, new_vendor.id, new_worker.id, actor, "rebalance route", expected_version=3
    )

    assert qualified_calls == [(booking, new_worker.id)]
    assert booking.provider_worker_id == new_worker.id
    assert released is harness.current
    assert released.status == AssignmentStatus.RELEASED and released.released_at is not None
    assert replacement.status == AssignmentStatus.ACTIVE
    assert (replacement.vendor_id, replacement.worker_id) == (new_vendor.id, new_worker.id)
    assert replacement.assigned_by == actor
    assert result is job and job.status == JobStatus.ASSIGNED and job.version == 4
    assert (job.vendor_id, job.worker_id) == (new_vendor.id, new_worker.id)
    # The previous row is released and flushed before the replacement is inserted.
    assert harness.calls.index("flush") < harness.calls.index("add:Assignment")
    assert harness.calls[-1] == "commit"

    [event] = harness.events
    assert event.from_status == event.to_status == JobStatus.ASSIGNED
    assert event.reason == "rebalance route" and event.actor_type == "operations"
    assert event.metadata_["previous_worker_id"] == str(previous_worker)
    assert event.metadata_["worker_id"] == str(new_worker.id)
    [audit] = [item for item in harness.added if isinstance(item, AuditLog)]
    assert audit.action == "assignment.reassign" and audit.actor_id == actor
    assert audit.metadata_json["released_assignment_id"] == str(released.id)
    assert audit.metadata_json["reason"] == "rebalance route"


@pytest.mark.asyncio
async def test_concurrent_reassignment_maps_integrity_error_to_conflict() -> None:
    job = make_job()
    harness = Harness(job)
    harness.session.commit = AsyncMock(side_effect=IntegrityError("insert", {}, Exception()))
    with pytest.raises(HTTPException) as raised:
        await harness.service.reassign(job.id, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "r")
    assert raised.value.status_code == 409
    harness.session.rollback.assert_awaited_once()
