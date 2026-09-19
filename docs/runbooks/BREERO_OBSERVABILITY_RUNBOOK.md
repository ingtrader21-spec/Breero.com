# BREERO production observability

## Release contract

BREERO emits three telemetry signals without exposing customer payloads:

- Prometheus metrics at the private API route `/metrics` when `METRICS_ENABLED=true`.
- OTLP/HTTP traces to `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` when `OTEL_ENABLED=true`.
- JSON logs on stdout. Codestra Alloy selects only containers labeled `com.codestra.product=breero` and ships those records to the corporate Loki writer.

The API uses route templates rather than raw URLs for metric labels and structured request logs. Request bodies, query strings, email addresses, authorization headers, cookies, and customer identifiers are not metric labels or trace attributes.

## Production apply

Apply the canonical hardened backend manifest together with the observability overlay:

```bash
docker compose \
  -f docker-compose.production.yml \
  -f deploy/observability/docker-compose.observability.yml \
  --env-file /etc/codestra/breero/production.env \
  config --quiet
```

Bind `BREERO_OTLP_TRACES_ENDPOINT` to the private collector address. Store collector authorization headers in a root-owned file as comma-separated `key=value` pairs and set `BREERO_OTLP_HEADERS_FILE_REFERENCE` to that host path. Compose mounts it read-only at `/run/secrets/breero_otlp_headers`. Do not expose `/metrics` through Caddy or Kong; Prometheus must scrape it over the private Docker network.

The API command in the overlay initializes `PROMETHEUS_MULTIPROC_DIR` once before uvicorn forks two workers. Do not remove that initialization while multiple workers are configured.

## Required alerts

| Alert | Production threshold |
| --- | --- |
| API unavailable | `up{job="breero-api"} == 0` for 2 minutes |
| Elevated 5xx | 5xx ratio above 2% for 10 minutes |
| p95 latency | above 1.5 seconds for 10 minutes |
| PostgreSQL or Redis unhealthy | `breero_dependency_up == 0` for 2 minutes |
| Outbox terminal failures | any `FAILED_TERMINAL` for 5 minutes |
| Oldest pending event | older than 300 seconds |
| Celery worker heartbeat | absent (`-1`) or older than 90 seconds |

## Verification

1. Confirm `/health/live` and `/health/ready` return 200 from the private network.
2. Scrape `/metrics` twice and confirm `breero_http_requests_total`, latency histograms, dependency gauges, outbox gauges, and worker heartbeat age are present.
3. Generate one staging request with an `X-Correlation-ID`; verify the same correlation ID appears in Loki and the trace ID links to Tempo.
4. Stop the worker in staging. The heartbeat age must cross 90 seconds and alert. Restart it and confirm recovery.
5. Confirm no raw email, phone, address, bearer token, cookie, request body, query string, or resource identifier appears in Prometheus, Tempo, or request-completion logs.

## Rollback

Disable `OTEL_ENABLED`, remove the observability Compose overlay, and redeploy the prior immutable image. Metrics and tracing are passive; rollback does not require a database migration.
