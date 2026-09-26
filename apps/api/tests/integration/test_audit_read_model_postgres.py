import os
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.db.session import get_db
from app.domains.audit.catalog import (
    ACCESS_ASSIGNMENTS_REPLACED_ACTION,
    ACCESS_DENIED_ACTION,
    AuditCategory,
    AuditResult,
)
from app.domains.audit.repository import AuditQuery
from app.domains.audit.service import AuditReadService
from app.domains.auth.dependencies import current_user
from app.domains.auth.models import User, UserRole
from app.domains.common.outbox import AuditLog, EventStatus, IntegrationEvent
from app.domains.common.outbox_service import OutboxService
from app.main import app

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL", "").startswith("postgresql"),
    reason="audit read model integration requires PostgreSQL",
)


@pytest.fixture
async def factory():
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


def _user(role: UserRole, marker: str) -> User:
    return User(
        # example.com, not .test: UserRead's EmailStr rejects special-use domains.
        email=f"audit-{role.value}-{marker}@example.com",
        password_hash="disabled",
        full_name=f"Audit {role.value}",
        role=role,
        is_active=True,
        email_verified=True,
    )


async def _client(factory, principal: User) -> httpx.AsyncClient:
    async def override_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[current_user] = lambda: principal
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://audit.test")


async def test_filters_and_keyset_pagination_are_exact_and_stable(factory) -> None:
    marker = uuid.uuid4().hex
    actor_id, vendor_id, resource_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    base = datetime.now(UTC).replace(microsecond=0) - timedelta(hours=1)
    rows = [
        AuditLog(
            actor_id=actor_id,
            actor_type="admin",
            action=action,
            resource_type="payout_batch",
            resource_id=resource_id,
            metadata_json={"vendor_id": str(vendor_id), "token": "never-stored"},
            # Two rows share a timestamp to prove the id tie-breaker.
            created_at=base + timedelta(minutes=min(index, 3)),
            result=result,
            correlation_id=f"corr-{marker}",
        )
        for index, (action, result) in enumerate(
            [
                ("payout.review", "success"),
                ("payout.approve", "success"),
                ("payout.submit", "failure"),
                ("payout.submit", "success"),
                ("service_zone.update", "success"),
            ]
        )
    ]
    async with factory() as session:
        session.add_all(rows)
        await session.commit()
        stored = list(
            (await session.scalars(select(AuditLog).where(AuditLog.actor_id == actor_id))).all()
        )
        assert all(row.metadata_json["token"] == "[REDACTED]" for row in stored)
        assert all(row.vendor_id == vendor_id for row in stored)

        service = AuditReadService(session)
        window = {"occurred_from": base - timedelta(minutes=1), "occurred_to": base + timedelta(hours=1)}

        seen: list[uuid.UUID] = []
        cursor = None
        while True:
            page = await service.search(
                AuditQuery(**window, actor_id=actor_id), limit=2, cursor=cursor
            )
            seen.extend(item.id for item in page.items)
            cursor = page.next_cursor
            if cursor is None:
                break
        expected = [
            row.id for row in sorted(stored, key=lambda r: (r.created_at, r.id), reverse=True)
        ]
        assert seen == expected

        async def ids(**filters) -> set[uuid.UUID]:
            page = await service.search(AuditQuery(**window, actor_id=actor_id, **filters), limit=100)
            return {item.id for item in page.items}

        by_action = {row.action: row.id for row in stored if row.result == "success"}
        assert await ids(action="payout.approve") == {by_action["payout.approve"]}
        assert len(await ids(action_prefix="payout.")) == 4
        assert len(await ids(result=AuditResult.failure)) == 1
        assert await ids(category=AuditCategory.privileged_admin) == {
            by_action["service_zone.update"]
        }
        assert len(await ids(category=AuditCategory.finance)) == 4
        assert len(await ids(vendor_id=vendor_id, resource_id=resource_id)) == 5
        assert len(await ids(correlation_id=f"corr-{marker}")) == 5
        assert await ids(correlation_id="corr-other") == set()
        security = await service.security_activity(AuditQuery(**window, actor_id=actor_id), limit=100)
        # approve + both submits (one failed) + geography admin change; review is not security.
        assert {item.action for item in security.items} == {
            "payout.approve",
            "payout.submit",
            "service_zone.update",
        }
        assert len(security.items) == 4

        trace = await service.trace(f"corr-{marker}")
        assert [item.id for item in trace.items] == list(reversed(expected))
        assert all("token" not in item.metadata for item in trace.items)

        await session.execute(delete(AuditLog).where(AuditLog.actor_id == actor_id))
        await session.commit()


async def test_role_change_and_denial_are_emitted_with_request_context(factory) -> None:
    marker = uuid.uuid4().hex
    admin, target, provider = (
        _user(UserRole.admin, marker),
        _user(UserRole.operations, marker),
        _user(UserRole.vendor_admin, marker),
    )
    async with factory() as session:
        session.add_all([admin, target, provider])
        await session.commit()
        for user in (admin, target, provider):
            await session.refresh(user)

    try:
        async with await _client(factory, admin) as client:
            changed = await client.put(
                f"/api/v1/auth/access/users/{target.id}",
                headers={"X-Correlation-ID": f"role-{marker}"},
                json={
                    "brand_key": "breero",
                    "assignments": [
                        {
                            "role": "support",
                            "department": "customer_support",
                            "tenant_scope": "brand",
                            "is_primary": True,
                        }
                    ],
                },
            )
            assert changed.status_code == 200, changed.text

            trace = await client.get(f"/api/v1/admin/audit/correlations/role-{marker}")
            assert trace.status_code == 200
            (event,) = trace.json()["items"]
            assert event["action"] == ACCESS_ASSIGNMENTS_REPLACED_ACTION
            assert event["category"] == "access_change"
            assert event["actor"] == {"id": str(admin.id), "type": "admin"}
            assert event["metadata"]["new_roles"] == ["support"]
            assert event["metadata"]["previous_roles"] == []
            assert event["source_fingerprint"] and len(event["source_fingerprint"]) == 16

        async with await _client(factory, provider) as client:
            denied = await client.get(
                "/api/v1/admin/audit/events", headers={"X-Correlation-ID": f"deny-{marker}"}
            )
            assert denied.status_code == 403
            assert "items" not in denied.text

        async with factory() as session:
            row = await session.scalar(
                select(AuditLog).where(AuditLog.correlation_id == f"deny-{marker}")
            )
            assert row is not None
            assert row.action == ACCESS_DENIED_ACTION and row.result == "denied"
            assert row.actor_id == provider.id
            assert row.metadata_json["required"] == ["admin.audit.read"]

        async with await _client(factory, admin) as client:
            security = await client.get(
                "/api/v1/admin/audit/security-events",
                params={"actor_id": str(provider.id), "result": "denied"},
            )
            assert security.status_code == 200
            assert [item["action"] for item in security.json()["items"]] == [ACCESS_DENIED_ACTION]
    finally:
        app.dependency_overrides.clear()
        async with factory() as session:
            await session.execute(
                delete(AuditLog).where(AuditLog.actor_id.in_([admin.id, provider.id]))
            )
            await session.execute(delete(User).where(User.id.in_([admin.id, target.id, provider.id])))
            await session.commit()


async def test_integration_retry_audit_is_structured_and_error_text_is_withheld(factory) -> None:
    event_id, actor_id = uuid.uuid4(), uuid.uuid4()
    async with factory() as session:
        session.add(
            IntegrationEvent(
                id=event_id,
                aggregate_id=uuid.uuid4(),
                aggregate_type="job",
                event_type="job.completed",
                payload={"fixture": "audit"},
                status=EventStatus.FAILED_TERMINAL,
                attempt_count=5,
                next_attempt_at=datetime.now(UTC),
                # Assembled at runtime so secret scanners do not flag the fixture.
                last_error="upstream said api_key=" + "_".join(["sk", "live", "abcdefghijklmnop"]),
                last_error_code="UPSTREAM_REJECTED",
            )
        )
        await session.commit()
        await OutboxService(session).retry(event_id, actor_id)

        page = await AuditReadService(session).search(
            AuditQuery(
                occurred_from=datetime.now(UTC) - timedelta(minutes=5),
                occurred_to=datetime.now(UTC) + timedelta(minutes=1),
                resource_id=event_id,
            )
        )
        (summary,) = page.items
        assert summary.category == "integration" and summary.security_relevant
        detail = await AuditReadService(session).detail(summary.id)
        assert detail.metadata == {
            "aggregate_type": "job",
            "event_type": "job.completed",
            "previous_error_code": "UPSTREAM_REJECTED",
            "previous_status": "FAILED_TERMINAL",
        }
        assert "sk_live" not in detail.model_dump_json()

        await session.execute(delete(AuditLog).where(AuditLog.resource_id == event_id))
        await session.execute(delete(IntegrationEvent).where(IntegrationEvent.id == event_id))
        await session.commit()
