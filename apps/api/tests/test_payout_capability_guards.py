import uuid
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.domains.finance.service import FinanceService
from app.integrations.payouts import FakePayoutGateway
from app.workers import tasks


@pytest.mark.parametrize("command,args", [
    ("release_eligible", ()),
    ("create_batch", ("USD",)),
    ("approve_batch", (uuid.uuid4(), uuid.uuid4())),
    ("submit_batch", (uuid.uuid4(), uuid.uuid4())),
])
async def test_disabled_commands_never_touch_database_or_gateway(monkeypatch, command, args):
    session = Mock(spec=AsyncSession)
    gateway = FakePayoutGateway()
    monkeypatch.setattr(settings, "payout_enabled", True)
    service = FinanceService(session, gateway)
    # A service constructed while enabled cannot retain authority after disablement.
    monkeypatch.setattr(settings, "payout_enabled", False)
    with pytest.raises(HTTPException) as error:
        await getattr(service, command)(*args)
    assert (error.value.status_code, error.value.detail) == (503, "payouts_disabled")
    assert session.mock_calls == []
    assert gateway.transfers == {}


async def test_enabled_batch_command_preserves_no_candidates_failure(monkeypatch):
    monkeypatch.setattr(settings, "payout_enabled", True)
    service = FinanceService(Mock(spec=AsyncSession), FakePayoutGateway())
    service.repo.available_earnings = AsyncMock(return_value=[])
    with pytest.raises(HTTPException) as error:
        await service.create_batch("USD")
    assert (error.value.status_code, error.value.detail) == (409, "No available earnings")
    service.repo.available_earnings.assert_awaited_once_with("USD", None, lock=True)


@pytest.mark.parametrize("task", [tasks.release_earnings, tasks.generate_weekly_payout_candidates])
def test_queued_finance_tasks_fail_visibly_when_disabled(monkeypatch, task):
    monkeypatch.setattr(settings, "payout_enabled", False)
    # Real service guard runs through the synchronous Celery entrypoint. No DB needed.
    with pytest.raises(HTTPException) as error:
        task.run()
    assert (error.value.status_code, error.value.detail) == (503, "payouts_disabled")
