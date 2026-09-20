from sqlalchemy.pool import NullPool

from app.db.worker_session import WorkerSessionLocal, worker_engine
from app.workers import tasks


def test_worker_engine_never_reuses_connections_across_task_event_loops() -> None:
    assert isinstance(worker_engine.sync_engine.pool, NullPool)
    assert WorkerSessionLocal.kw["bind"] is worker_engine


def test_every_celery_task_uses_worker_session_factory() -> None:
    assert tasks.WorkerSessionLocal is WorkerSessionLocal


def test_worker_tracing_instruments_the_worker_engine(monkeypatch) -> None:
    from unittest.mock import Mock

    from app import observability

    provider = object()
    sql = Mock()
    monkeypatch.setattr(observability, "configure_logging", Mock())
    monkeypatch.setattr(observability, "_tracer_provider", lambda: provider)
    monkeypatch.setattr(observability, "SQLAlchemyInstrumentor", lambda: sql)
    monkeypatch.setattr(observability, "CeleryInstrumentor", Mock())
    monkeypatch.setattr(observability, "RedisInstrumentor", Mock())

    observability.configure_worker_observability()

    sql.instrument.assert_called_once_with(
        engine=worker_engine.sync_engine, tracer_provider=provider
    )
