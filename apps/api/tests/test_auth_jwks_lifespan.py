import asyncio

import pytest
from fastapi import FastAPI

from app.config import settings
from app.core import lifespan as lifespan_module


class FakeConnection:
    def __init__(self) -> None:
        self.warmed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def execute(self, statement) -> None:
        self.warmed = True


class FakeEngine:
    def __init__(self) -> None:
        self.connection = FakeConnection()
        self.disposed = False

    def connect(self) -> FakeConnection:
        return self.connection

    async def dispose(self) -> None:
        self.disposed = True


class FakeRedis:
    def __init__(self) -> None:
        self.pinged = False
        self.closed = False

    async def ping(self) -> bool:
        self.pinged = True
        return True

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_lifespan_owns_and_closes_all_process_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = asyncio.Event()
    stopped = asyncio.Event()
    fake_engine = FakeEngine()
    fake_redis = FakeRedis()

    async def fake_maintain(stop: asyncio.Event) -> None:
        started.set()
        await stop.wait()
        stopped.set()

    monkeypatch.setattr(settings, "keycloak_enabled", True)
    monkeypatch.setattr(lifespan_module, "maintain_keycloak_jwks", fake_maintain)
    monkeypatch.setattr(lifespan_module, "engine", fake_engine)
    monkeypatch.setattr(lifespan_module, "create_redis_client", lambda: fake_redis)

    app = FastAPI()
    async with lifespan_module.lifespan(app):
        await asyncio.wait_for(started.wait(), timeout=1)
        assert app.state.redis is fake_redis
        assert fake_engine.connection.warmed
        assert fake_redis.pinged

    assert stopped.is_set()
    assert app.state.redis is None
    assert fake_redis.closed
    assert fake_engine.disposed
