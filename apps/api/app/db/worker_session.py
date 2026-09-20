from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings

# Celery tasks create a fresh asyncio loop per invocation. NullPool guarantees
# every async connection is opened and closed inside that same loop instead of
# being reused by a later task whose loop is different.
worker_engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    poolclass=NullPool,
)
WorkerSessionLocal = async_sessionmaker(
    worker_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
