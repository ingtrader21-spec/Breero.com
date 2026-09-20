from __future__ import annotations

import logging
import os
import re
import time
from collections.abc import MutableMapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import redis as redis_sync
import redis.asyncio as redis_async
import structlog
from fastapi import FastAPI, Request, Response
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from prometheus_client import (
    REGISTRY,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from prometheus_client.exposition import CONTENT_TYPE_LATEST
from prometheus_client.multiprocess import MultiProcessCollector
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import func, select

from app.config import settings
from app.db.session import SessionLocal, engine
from app.domains.common.outbox import EventStatus, IntegrationEvent


class ObservabilitySettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    metrics_path: str = "/metrics"
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"
    otel_enabled: bool = False
    otel_service_name: str = "breero-api"
    otel_exporter_otlp_traces_endpoint: str = ""
    otel_exporter_otlp_headers_file: str = ""
    otel_exporter_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    otel_trace_sample_ratio: float = Field(default=0.1, ge=0, le=1)
    otel_excluded_urls: str = "health,metrics"
    runtime_heartbeat_key: str = "breero:runtime:heartbeat"

    @model_validator(mode="after")
    def validate_exporter(self) -> "ObservabilitySettings":
        if self.otel_enabled and not self.otel_exporter_otlp_traces_endpoint:
            raise ValueError("OTEL exporter endpoint is required when tracing is enabled")
        if self.otel_exporter_otlp_headers_file and not Path(
            self.otel_exporter_otlp_headers_file
        ).is_file():
            raise ValueError("configured OTLP headers file is not readable")
        return self


observability_settings = ObservabilitySettings()

_SAFE_ROUTE = re.compile(r"^/[A-Za-z0-9_{}./:-]{1,255}$")
_PENDING_OUTBOX_STATUSES = (
    EventStatus.PENDING,
    EventStatus.PENDING_CONFIGURATION,
    EventStatus.PROCESSING,
    EventStatus.RETRYING,
    EventStatus.FAILED_RETRYABLE,
)

HTTP_REQUESTS = Counter(
    "breero_http_requests_total",
    "BREERO HTTP requests completed.",
    ("method", "route", "status_code"),
)
HTTP_REQUEST_DURATION = Histogram(
    "breero_http_request_duration_seconds",
    "BREERO HTTP request latency.",
    ("method", "route"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
DEPENDENCY_UP = Gauge(
    "breero_dependency_up",
    "Whether a required BREERO dependency is healthy.",
    ("dependency",),
    multiprocess_mode="max",
)
OUTBOX_EVENTS = Gauge(
    "breero_outbox_events",
    "Current durable outbox events by status.",
    ("status",),
    multiprocess_mode="max",
)
OUTBOX_OLDEST_PENDING_AGE = Gauge(
    "breero_outbox_oldest_pending_age_seconds",
    "Age of the oldest pending durable outbox event.",
    multiprocess_mode="max",
)
WORKER_HEARTBEAT_AGE = Gauge(
    "breero_worker_heartbeat_age_seconds",
    "Age of the latest Celery worker heartbeat.",
    multiprocess_mode="max",
)


def _trace_fields(
    _logger: Any,
    _method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    context = trace.get_current_span().get_span_context()
    if context.is_valid:
        event_dict["trace_id"] = format(context.trace_id, "032x")
        event_dict["span_id"] = format(context.span_id, "016x")
    return event_dict


def configure_logging() -> None:
    level = getattr(logging, observability_settings.log_level.upper(), logging.INFO)
    logging.basicConfig(level=level, format="%(message)s", force=True)
    renderer: Any
    if observability_settings.log_format == "console":
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _trace_fields,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def _read_headers(path: str) -> dict[str, str] | None:
    if not path:
        return None
    raw = Path(path).read_text(encoding="utf-8").strip()
    if not raw:
        return None
    headers: dict[str, str] = {}
    for pair in raw.split(","):
        key, separator, value = pair.partition("=")
        if not separator or not key.strip() or "\n" in value or "\r" in value:
            raise ValueError("OTLP header file must contain comma-separated key=value pairs")
        headers[key.strip()] = value.strip()
    return headers


def _tracer_provider() -> TracerProvider | None:
    if not observability_settings.otel_enabled:
        return None
    resource = Resource.create(
        {
            "service.name": observability_settings.otel_service_name,
            "service.namespace": "breero",
            "deployment.environment.name": settings.app_env,
        }
    )
    provider = TracerProvider(
        resource=resource,
        sampler=ParentBased(TraceIdRatioBased(observability_settings.otel_trace_sample_ratio)),
    )
    exporter = OTLPSpanExporter(
        endpoint=observability_settings.otel_exporter_otlp_traces_endpoint,
        headers=_read_headers(observability_settings.otel_exporter_otlp_headers_file),
        timeout=observability_settings.otel_exporter_timeout_seconds,
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return provider


def configure_tracing(app: FastAPI) -> None:
    provider = _tracer_provider()
    if provider is None:
        return
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=provider,
        excluded_urls=observability_settings.otel_excluded_urls,
    )
    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine, tracer_provider=provider)
    RedisInstrumentor().instrument(tracer_provider=provider)


def configure_worker_observability() -> None:
    configure_logging()
    provider = _tracer_provider()
    if provider is None:
        return
    from app.db.worker_session import worker_engine

    CeleryInstrumentor().instrument(tracer_provider=provider)
    SQLAlchemyInstrumentor().instrument(engine=worker_engine.sync_engine, tracer_provider=provider)
    RedisInstrumentor().instrument(tracer_provider=provider)


def record_worker_heartbeat() -> None:
    client = redis_sync.from_url(
        settings.redis_url,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    try:
        client.set(observability_settings.runtime_heartbeat_key, str(time.time()), ex=90)
    except Exception:
        structlog.get_logger().exception("worker_heartbeat_write_failed")
    finally:
        client.close()


def route_template(request: Request) -> str:
    route = request.scope.get("route")
    value = getattr(route, "path", None)
    if isinstance(value, str) and _SAFE_ROUTE.fullmatch(value):
        return value
    return "unmatched"


def record_http_request(request: Request, status_code: int, duration_seconds: float) -> None:
    if not settings.metrics_enabled or request.url.path == observability_settings.metrics_path:
        return
    method = request.method.upper()
    route = route_template(request)
    HTTP_REQUESTS.labels(method=method, route=route, status_code=str(status_code)).inc()
    HTTP_REQUEST_DURATION.labels(method=method, route=route).observe(duration_seconds)


def record_dependency(name: str, healthy: bool) -> None:
    if settings.metrics_enabled:
        DEPENDENCY_UP.labels(dependency=name).set(1 if healthy else 0)


def _registry() -> CollectorRegistry:
    multiprocess_directory = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if not multiprocess_directory:
        return REGISTRY
    registry = CollectorRegistry()
    MultiProcessCollector(registry)
    return registry


async def _refresh_operational_metrics() -> None:
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(IntegrationEvent.status, func.count(IntegrationEvent.id)).group_by(
                    IntegrationEvent.status
                )
            )
        ).all()
        counts = {status: int(count) for status, count in rows}
        for status in EventStatus:
            OUTBOX_EVENTS.labels(status=status.value).set(counts.get(status, 0))
        oldest = await session.scalar(
            select(func.min(IntegrationEvent.created_at)).where(
                IntegrationEvent.status.in_(_PENDING_OUTBOX_STATUSES)
            )
        )
        if oldest:
            if oldest.tzinfo is None:
                oldest = oldest.replace(tzinfo=UTC)
            OUTBOX_OLDEST_PENDING_AGE.set(
                max(0.0, (datetime.now(UTC) - oldest).total_seconds())
            )
        else:
            OUTBOX_OLDEST_PENDING_AGE.set(0)

    client = redis_async.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)
    try:
        raw = await client.get(observability_settings.runtime_heartbeat_key)
        if raw is None:
            WORKER_HEARTBEAT_AGE.set(-1)
            return
        timestamp = datetime.fromtimestamp(float(raw), tz=UTC)
        WORKER_HEARTBEAT_AGE.set(max(0.0, (datetime.now(UTC) - timestamp).total_seconds()))
    finally:
        await client.aclose()


async def metrics_response() -> Response:
    try:
        await _refresh_operational_metrics()
        record_dependency("metrics_storage", True)
    except Exception:
        # Scrapes remain available for process/HTTP metrics even when dependencies fail.
        record_dependency("metrics_storage", False)
        structlog.get_logger().exception("operational_metrics_refresh_failed")
    return Response(content=generate_latest(_registry()), media_type=CONTENT_TYPE_LATEST)
