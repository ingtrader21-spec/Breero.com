"""Exercise real connections across the synchronous Celery task loop boundary."""
import asyncio
import os

import pytest
from sqlalchemy import text

from app.db.worker_session import WorkerSessionLocal
from app.workers.tasks import expire_bookings

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL", "").startswith("postgresql"),
    reason="requires isolated PostgreSQL/PostGIS",
)


def test_each_task_loop_opens_and_closes_its_own_postgres_connection():
    async def probe():
        async with WorkerSessionLocal() as session:
            return await session.scalar(text("SELECT pg_backend_pid()"))

    first_pid = asyncio.run(probe())
    second_pid = asyncio.run(probe())
    assert first_pid != second_pid

    async def connection_is_closed(pid):
        async with WorkerSessionLocal() as session:
            return await session.scalar(
                text("SELECT count(*) FROM pg_stat_activity WHERE pid = :pid"), {"pid": pid}
            ) == 0

    assert asyncio.run(connection_is_closed(first_pid))
    assert asyncio.run(connection_is_closed(second_pid))


def test_expiry_task_can_run_repeatedly_in_one_worker_process():
    # Each invocation creates and closes a distinct asyncio loop. No broker or
    # provider is invoked; the configured database is an isolated test database.
    first_count = expire_bookings.run()
    second_count = expire_bookings.run()
    assert first_count >= 0
    assert second_count == 0
