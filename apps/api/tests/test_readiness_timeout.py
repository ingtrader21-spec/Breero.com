import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

import pytest
from fastapi import HTTPException

from app import main


@pytest.fixture
def dependencies(monkeypatch):
    connection = SimpleNamespace(scalar=AsyncMock(return_value=main.EXPECTED_SCHEMA_REVISION))
    client = SimpleNamespace(ping=AsyncMock(return_value=True), aclose=AsyncMock())
    released = []
    metrics = Mock()
    monkeypatch.setattr(main, "record_dependency", metrics)

    @asynccontextmanager
    async def connect():
        try:
            yield connection
        finally:
            released.append(True)

    monkeypatch.setattr(main, "engine", SimpleNamespace(connect=connect))
    monkeypatch.setattr(main, "redis_client_from_request", lambda request: client)
    monkeypatch.setattr(main, "READINESS_TIMEOUT_SECONDS", 0.02)
    return connection, client, released


@pytest.mark.asyncio
@pytest.mark.parametrize("dependency", ["postgres", "redis"])
async def test_stalled_dependency_returns_503_and_releases_resources(dependencies, dependency):
    connection, client, released = dependencies

    async def stall(*args):
        await asyncio.Event().wait()

    if dependency == "postgres":
        connection.scalar.side_effect = stall
    else:
        client.ping.side_effect = stall

    with pytest.raises(HTTPException) as error:
        await asyncio.wait_for(main.ready(SimpleNamespace()), timeout=1)

    assert error.value.status_code == 503
    assert error.value.detail == "dependency unavailable"
    assert released == [True]
    if dependency == "redis":
        client.aclose.assert_not_awaited()
    else:
        client.ping.assert_not_awaited()
    main.record_dependency.assert_any_call(dependency, False)


@pytest.mark.asyncio
async def test_healthy_dependencies_preserve_readiness_response(dependencies):
    _, client, released = dependencies
    assert await main.ready(SimpleNamespace()) == {
        "status": "ready", "postgres": "ok", "schema": "ok", "redis": "ok"
    }
    assert released == [True]
    client.aclose.assert_not_awaited()
    assert main.record_dependency.call_args_list == [
        call("postgres", True), call("schema", True), call("redis", True)
    ]


@pytest.mark.asyncio
async def test_outdated_schema_still_returns_not_ready(dependencies):
    connection, _, _ = dependencies
    connection.scalar.return_value = "outdated"
    with pytest.raises(HTTPException) as error:
        await main.ready(SimpleNamespace())
    assert error.value.status_code == 503
    assert error.value.detail["checks"]["schema"] == "outdated"


@pytest.mark.asyncio
async def test_connection_acquisition_timeout_is_not_reported_as_healthy(dependencies, monkeypatch):
    _, client, _ = dependencies

    @asynccontextmanager
    async def stalled_connect():
        await asyncio.Event().wait()
        yield

    monkeypatch.setattr(main, "engine", SimpleNamespace(connect=stalled_connect))
    with pytest.raises(HTTPException) as error:
        await asyncio.wait_for(main.ready(SimpleNamespace()), timeout=1)
    assert error.value.status_code == 503
    client.ping.assert_not_awaited()
    assert main.record_dependency.call_args_list == [
        call("postgres", False), call("schema", False)
    ]


@pytest.mark.asyncio
async def test_dependency_failure_logs_only_safe_context(dependencies, monkeypatch):
    connection, _, _ = dependencies
    connection.scalar.side_effect = RuntimeError("private-connection-details")
    log = Mock()
    monkeypatch.setattr(main, "logger", log)
    with pytest.raises(HTTPException) as error:
        await main.ready(SimpleNamespace())
    assert error.value.detail == "dependency unavailable"
    log.warning.assert_called_once_with(
        "readiness_failed", dependency="postgres", error="RuntimeError"
    )
