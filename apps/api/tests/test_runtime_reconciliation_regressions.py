import uuid
from datetime import UTC, date, datetime, time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from app.api.v1 import auth
from app.domains.booking.matching import ProviderMatcher
from app.domains.workforce.provider_schemas import AvailabilityRuleRead, AvailabilityRuleWrite
from app.domains.workforce.provider_service import ProviderPortalService


def test_csrf_channel_is_origin_restricted_and_never_returns_session_tokens(monkeypatch):
    monkeypatch.setattr(auth, "settings", SimpleNamespace(allowed_origins=["https://breero.com"]))
    app = FastAPI()
    app.include_router(auth.router, prefix="/auth")
    with TestClient(app, base_url="https://api.breero.com") as client:
        assert client.get("/auth/csrf", headers={"Origin": "https://breero.com"}).status_code == 401
        client.cookies.set("breero_csrf", "synthetic-csrf")
        client.cookies.set("breero_refresh", "synthetic-private-refresh")
        good = client.get("/auth/csrf", headers={"Origin": "https://breero.com"})
        assert good.status_code == 200
        assert good.json() == {"csrf_token": "synthetic-csrf"}
        assert good.headers["cache-control"] == "no-store"
        bad = client.get("/auth/csrf", headers={"Origin": "https://evil.example"})
        assert bad.status_code == 403
        assert "synthetic-csrf" not in bad.text


@pytest.mark.asyncio
@pytest.mark.parametrize("empty", [True, False])
async def test_availability_replacement_scopes_delete_to_all_vendor_workers(empty):
    vendor_id, worker_id = uuid.uuid4(), uuid.uuid4()
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    service = ProviderPortalService(session, SimpleNamespace(id=uuid.uuid4()))
    service.context = AsyncMock(return_value=(SimpleNamespace(id=vendor_id), None))
    service._owned_worker = AsyncMock()
    service._audit = MagicMock()
    rules = [] if empty else [AvailabilityRuleWrite(
        professional_id=worker_id, day_of_week=1, start_local_time=time(9),
        end_local_time=time(17), timezone_id="America/Chicago",
    )]
    records = await service.replace_availability(rules)
    statement = session.execute.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "SELECT workers.id" in sql
    assert str(vendor_id) in sql
    assert str(worker_id) not in sql
    if not empty:
        record = records[0]
        assert record.provider_professional_id == worker_id
        record.id = uuid.uuid4()
        assert AvailabilityRuleRead.model_validate(record).professional_id == worker_id
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_usage_reserves_converted_hold_without_job_and_avoids_double_counting():
    session = MagicMock()
    hold = SimpleNamespace(capacity_minutes=60, slot_start_utc=datetime(2026, 9, 22, 9, tzinfo=UTC),
                           slot_end_utc=datetime(2026, 9, 22, 10, tzinfo=UTC))
    session.scalars = AsyncMock(side_effect=[SimpleNamespace(all=lambda: []), SimpleNamespace(all=lambda: [hold])])
    usage, overlaps = await ProviderMatcher(session)._usage(
        uuid.uuid4(), date(2026, 9, 22), hold.slot_start_utc, hold.slot_end_utc, UTC,
    )
    assert usage.hold_count == 1 and usage.hold_minutes == 60 and overlaps == 1
    sql = str(session.scalars.call_args.args[0].compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "CONVERTED" in sql and "HELD" in sql
    assert "NOT (EXISTS (SELECT jobs.id" in sql
    assert "jobs.booking_id = booking_capacity_holds.booking_id" in sql
    assert "CANCELLED" in sql and "EXPIRED" in sql and "COMPLETED" in sql
