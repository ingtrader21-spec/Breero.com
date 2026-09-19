from typing import cast

import redis.asyncio as redis
from fastapi import Request
from redis.asyncio import Redis

from app.config import settings


def create_redis_client() -> Redis:
    """Create the process-wide async Redis client and bounded connection pool."""

    return redis.from_url(
        settings.redis_url,
        max_connections=settings.redis_max_connections,
        socket_connect_timeout=settings.redis_socket_connect_timeout_seconds,
        socket_timeout=settings.redis_socket_timeout_seconds,
        health_check_interval=30,
        retry_on_timeout=False,
    )


def redis_client_from_request(request: Request) -> Redis | None:
    return cast(Redis | None, getattr(request.app.state, "redis", None))
