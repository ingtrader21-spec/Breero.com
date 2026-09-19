import pytest
from fastapi import FastAPI, HTTPException
from redis.exceptions import ConnectionError as RedisConnectionError
from starlette.requests import Request

from app.core import rate_limit as rate_limit_module


class AllowingRedis:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def eval(self, *args):
        self.calls.append(args)
        return [1, 0]


class FailingRedis:
    async def eval(self, *args):
        raise RedisConnectionError("redis unavailable")


def request_for(app: FastAPI, host: str = "203.0.113.10") -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/test",
            "headers": [],
            "query_string": b"",
            "scheme": "https",
            "server": ("api.example.test", 443),
            "client": (host, 50000),
            "app": app,
        }
    )


@pytest.fixture(autouse=True)
def clear_local_buckets() -> None:
    rate_limit_module._LOCAL_BUCKETS.clear()


@pytest.mark.asyncio
async def test_rate_limiter_reuses_lifespan_redis_client() -> None:
    app = FastAPI()
    client = AllowingRedis()
    app.state.redis = client

    await rate_limit_module.enforce_rate_limit(
        request_for(app),
        "login",
        10,
        60,
    )

    assert len(client.calls) == 1
    script, key_count, key, capacity, window_ms = client.calls[0]
    assert script == rate_limit_module.TOKEN_BUCKET_LUA
    assert key_count == 1
    assert key.startswith("ratelimit:login:")
    assert capacity == "10"
    assert window_ms == "60000"


@pytest.mark.asyncio
async def test_redis_outage_uses_local_bucket_instead_of_returning_503() -> None:
    app = FastAPI()
    app.state.redis = FailingRedis()
    request = request_for(app)

    await rate_limit_module.enforce_rate_limit(request, "public-form", 1, 60)

    with pytest.raises(HTTPException) as error:
        await rate_limit_module.enforce_rate_limit(request, "public-form", 1, 60)
    assert error.value.status_code == 429
    assert int(error.value.headers["Retry-After"]) >= 1


@pytest.mark.asyncio
async def test_missing_lifespan_client_uses_same_bounded_local_fallback() -> None:
    app = FastAPI()
    request = request_for(app, "203.0.113.11")

    await rate_limit_module.enforce_rate_limit(request, "webhook", 1, 60)

    with pytest.raises(HTTPException) as error:
        await rate_limit_module.enforce_rate_limit(request, "webhook", 1, 60)
    assert error.value.status_code == 429


def test_local_fallback_rejects_unseen_identity_at_hard_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rate_limit_module, "LOCAL_BUCKET_MAX_KEYS", 2)

    assert rate_limit_module._consume_local_bucket("first", 1, 60) == (True, 0)
    assert rate_limit_module._consume_local_bucket("second", 1, 60) == (True, 0)

    allowed, retry_after = rate_limit_module._consume_local_bucket("third", 1, 60)

    assert allowed is False
    assert retry_after == 60
    assert set(rate_limit_module._LOCAL_BUCKETS) == {"first", "second"}


def test_source_comes_from_proxy_normalized_request_client() -> None:
    app = FastAPI()
    assert rate_limit_module.source_for_request(request_for(app)) == "203.0.113.10"
