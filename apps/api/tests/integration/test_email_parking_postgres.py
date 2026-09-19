import os
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.v1.integrations import failures
from app.config import settings
from app.domains.common.outbox import AuditLog, EventStatus, IntegrationEvent
from app.domains.common.outbox_service import MAX_ATTEMPTS, OutboxService
from app.integrations import email

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL", "").startswith("postgresql"), reason="requires isolated PostgreSQL",
)


async def test_disabled_email_parks_and_explicit_replay_rechecks_switch(monkeypatch):
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    event_id, actor_id = uuid.uuid4(), uuid.uuid4()
    monkeypatch.setattr(settings, "live_email_delivery", False)
    monkeypatch.setattr(settings, "email_enabled", True)
    monkeypatch.setattr(settings, "transactional_email_mode", "controlled_canary")
    monkeypatch.setenv("EMAIL_DELIVERY_URL", "https://email.example.invalid/send")
    client, context = AsyncMock(), AsyncMock()
    context.__aenter__.return_value = client
    client.post.return_value = httpx.Response(202, request=httpx.Request("POST", "https://email.example.invalid/send"))
    network = Mock(return_value=context)
    monkeypatch.setattr(email.httpx, "AsyncClient", network)
    adapter = email.EmailAdapter()

    async def deliver(event):
        await adapter.send(event.event_type, event.payload)

    try:
        async with factory() as session:
            session.add(IntegrationEvent(
                id=event_id, aggregate_id=uuid.uuid4(), aggregate_type="user",
                event_type="password_changed", payload={"fixture": "retained"},
                status=EventStatus.PENDING, attempt_count=MAX_ATTEMPTS,
                created_at=datetime(1970, 1, 1, tzinfo=UTC), next_attempt_at=datetime.now(UTC),
            ))
            await session.commit()
            assert await OutboxService(session).process(deliver, limit=1) == 1
        async with factory() as session:
            event = await session.get(IntegrationEvent, event_id)
            assert event.status == EventStatus.PENDING_CONFIGURATION
            assert event.last_error_code == "EMAIL_DELIVERY_DISABLED"
            assert event.attempt_count == MAX_ATTEMPTS + 1
            assert event.processed_at is None
            assert event.claim_token is None and event.lease_expires_at is None
            assert event.payload == {"fixture": "retained"}
            network.assert_not_called()
            assert event_id in [item.id for item in await failures(session, Mock())]
            outbox = OutboxService(session)
            await outbox.retry(event_id, actor_id)
            assert await outbox.process(deliver, limit=1) == 1
            await session.refresh(event)
            assert event.status == EventStatus.PENDING_CONFIGURATION
            network.assert_not_called()
            monkeypatch.setattr(settings, "live_email_delivery", True)
            await outbox.retry(event_id, actor_id)
            assert await outbox.process(deliver, limit=1) == 1
            await session.refresh(event)
            assert event.status == EventStatus.DELIVERED
            client.post.assert_awaited_once()
            audits = list((await session.scalars(select(AuditLog).where(
                AuditLog.resource_id == event_id, AuditLog.action == "integration.retry",
            ))).all())
            assert len(audits) == 2
            assert all(audit.actor_id == actor_id for audit in audits)
    finally:
        async with factory() as session:
            await session.execute(delete(AuditLog).where(AuditLog.resource_id == event_id))
            await session.execute(delete(IntegrationEvent).where(IntegrationEvent.id == event_id))
            await session.commit()
        await engine.dispose()
