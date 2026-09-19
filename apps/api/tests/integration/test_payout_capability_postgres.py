import os
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.domains.common.outbox import AuditLog, IntegrationEvent
from app.domains.finance.models import PayoutBatch, PayoutStatus
from app.domains.finance.service import FinanceService
from app.integrations.payouts import FakePayoutGateway

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL", "").startswith("postgresql"),
    reason="requires isolated PostgreSQL",
)


async def test_disabled_submission_preserves_batch_and_can_be_recovered(monkeypatch):
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    batch_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    gateway = FakePayoutGateway()
    try:
        async with factory() as session:
            session.add(PayoutBatch(
                id=batch_id, reference=f"guard-{batch_id}", status=PayoutStatus.APPROVED,
                currency="USD", total_minor=100, earning_count=1,
            ))
            await session.commit()
        async with factory() as session:
            service = FinanceService(session, gateway)
            monkeypatch.setattr(settings, "payout_enabled", False)
            with pytest.raises(HTTPException, match="payouts_disabled"):
                await service.submit_batch(batch_id, actor_id)
        async with factory() as session:
            batch = await session.get(PayoutBatch, batch_id)
            assert batch.status == PayoutStatus.APPROVED
            assert batch.idempotency_key is None
            assert batch.provider_transfer_id is None
            assert batch.failure_reason is None
            assert gateway.transfers == {}
            for model, column in ((AuditLog, AuditLog.resource_id),
                                  (IntegrationEvent, IntegrationEvent.aggregate_id)):
                assert await session.scalar(select(func.count()).select_from(model).where(
                    column == batch_id,
                )) == 0
            # Test-only enablement with a fake gateway proves retained work is recoverable.
            monkeypatch.setattr(settings, "payout_enabled", True)
            service = FinanceService(session, gateway)
            result = await service.submit_batch(batch_id, actor_id)
            assert result.status == PayoutStatus.PROCESSING
            transfer_id = result.provider_transfer_id
            assert len(gateway.transfers) == 1
            monkeypatch.setattr(settings, "payout_enabled", False)
            with pytest.raises(HTTPException, match="payouts_disabled"):
                await service.submit_batch(batch_id, actor_id)
            await session.refresh(result)
            assert result.provider_transfer_id == transfer_id
            assert len(gateway.transfers) == 1
    finally:
        async with factory() as session:
            await session.execute(delete(AuditLog).where(AuditLog.resource_id == batch_id))
            await session.execute(delete(IntegrationEvent).where(IntegrationEvent.aggregate_id == batch_id))
            await session.execute(delete(PayoutBatch).where(PayoutBatch.id == batch_id))
            await session.commit()
        await engine.dispose()
