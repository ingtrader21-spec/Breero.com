import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from sqlalchemy import text

from app.config import settings
from app.core.redis_client import create_redis_client
from app.db.session import engine
from app.domains.auth.security import maintain_keycloak_jwks


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Own process-wide database, Redis, and identity-key resources."""

    stop = asyncio.Event()
    jwks_task: asyncio.Task[None] | None = None
    redis_client = create_redis_client()
    app.state.redis = redis_client
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        await redis_client.ping()
        if settings.keycloak_enabled:
            jwks_task = asyncio.create_task(
                maintain_keycloak_jwks(stop),
                name="keycloak-jwks-refresh",
            )
        yield
    finally:
        stop.set()
        if jwks_task is not None:
            with suppress(asyncio.CancelledError):
                await jwks_task
        app.state.redis = None
        await redis_client.aclose()
        await engine.dispose()
