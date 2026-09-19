import hashlib
import math
import threading
import time
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import cast

import structlog
from fastapi import HTTPException, Request
from redis.exceptions import RedisError

from app.core.redis_client import redis_client_from_request

TOKEN_BUCKET_LUA = """
local current = redis.call("HMGET", KEYS[1], "tokens", "updated_at")
local clock = redis.call("TIME")
local now_ms = (tonumber(clock[1]) * 1000) + math.floor(tonumber(clock[2]) / 1000)
local capacity = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local refill_per_ms = capacity / window_ms
local tokens = tonumber(current[1])
local updated_at = tonumber(current[2])

if tokens == nil or updated_at == nil then
    tokens = capacity
else
    local elapsed = math.max(0, now_ms - updated_at)
    tokens = math.min(capacity, tokens + (elapsed * refill_per_ms))
end

local allowed = 0
local retry_ms = 0
if tokens >= 1 then
    tokens = tokens - 1
    allowed = 1
else
    retry_ms = math.ceil((1 - tokens) / refill_per_ms)
end

redis.call("HSET", KEYS[1], "tokens", tokens, "updated_at", now_ms)
redis.call("PEXPIRE", KEYS[1], math.ceil(window_ms * 2))
return {allowed, retry_ms}
"""

logger = structlog.get_logger()
LOCAL_BUCKET_MAX_KEYS = 1_024


@dataclass(slots=True)
class _LocalBucket:
    tokens: float
    updated_at: float
    expires_at: float


_LOCAL_BUCKETS: dict[str, _LocalBucket] = {}
_LOCAL_BUCKET_LOCK = threading.Lock()


def source_for_request(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _bucket_key(scope: str, source: str) -> str:
    identity = hashlib.sha256(source.encode()).hexdigest()[:24]
    return f"ratelimit:{scope}:{identity}"


def _consume_local_bucket(
    key: str,
    capacity: int,
    window_seconds: int,
) -> tuple[bool, int]:
    now = time.monotonic()
    refill_per_second = capacity / window_seconds
    with _LOCAL_BUCKET_LOCK:
        if len(_LOCAL_BUCKETS) >= LOCAL_BUCKET_MAX_KEYS:
            expired = [name for name, bucket in _LOCAL_BUCKETS.items() if bucket.expires_at <= now]
            for name in expired:
                _LOCAL_BUCKETS.pop(name, None)

        bucket = _LOCAL_BUCKETS.get(key)
        if bucket is not None and bucket.expires_at <= now:
            _LOCAL_BUCKETS.pop(key, None)
            bucket = None

        if bucket is None:
            # During a Redis outage, high-cardinality traffic must not make the
            # process-local safety fallback grow without bound. Reclaim expired
            # entries first, then fail closed for unseen identities at the cap.
            if len(_LOCAL_BUCKETS) >= LOCAL_BUCKET_MAX_KEYS:
                return False, max(1, window_seconds)
            bucket = _LocalBucket(
                tokens=float(capacity),
                updated_at=now,
                expires_at=now + (window_seconds * 2),
            )
        else:
            elapsed = max(0.0, now - bucket.updated_at)
            bucket.tokens = min(float(capacity), bucket.tokens + elapsed * refill_per_second)
            bucket.updated_at = now
            bucket.expires_at = now + (window_seconds * 2)
        allowed = bucket.tokens >= 1
        if allowed:
            bucket.tokens -= 1
            retry_after = 0
        else:
            retry_after = max(1, math.ceil((1 - bucket.tokens) / refill_per_second))
        _LOCAL_BUCKETS[key] = bucket
    return allowed, retry_after


def _raise_rate_limited(retry_after: int) -> None:
    raise HTTPException(
        429,
        "rate limit exceeded",
        headers={"Retry-After": str(max(1, retry_after))},
    )


async def enforce_rate_limit(
    request: Request,
    scope: str,
    requests: int,
    window_seconds: int,
) -> None:
    """Enforce an atomic token bucket, with a process-local outage fallback."""

    if requests < 1 or window_seconds < 1:
        raise ValueError("rate-limit capacity and window must be positive")
    source = source_for_request(request)
    key = _bucket_key(scope, source)
    client = redis_client_from_request(request)
    if client is not None:
        try:
            result = await cast(
                Awaitable[list[int]],
                client.eval(
                    TOKEN_BUCKET_LUA,
                    1,
                    key,
                    str(requests),
                    str(window_seconds * 1_000),
                ),
            )
            allowed, retry_ms = result
        except RedisError as exc:
            logger.warning(
                "rate_limit_redis_degraded",
                scope=scope,
                error=type(exc).__name__,
            )
        else:
            if not int(allowed):
                _raise_rate_limited(max(1, math.ceil(int(retry_ms) / 1_000)))
            return

    allowed, retry_after = _consume_local_bucket(key, requests, window_seconds)
    if not allowed:
        _raise_rate_limited(retry_after)


def rate_limit(scope: str, requests: int, window_seconds: int):
    async def enforce(request: Request) -> None:
        await enforce_rate_limit(request, scope, requests, window_seconds)

    return enforce
