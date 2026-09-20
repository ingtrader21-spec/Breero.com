# Worker database lifecycle

Milestone 1 / PR #105 keeps the synchronous Celery task interface and its existing
`asyncio.run` boundaries. Tasks use a worker-only SQLAlchemy engine with NullPool,
so a connection is created and closed within one task's event loop. The pooled
API engine is unchanged. Worker OpenTelemetry instrumentation follows the worker
engine; API instrumentation continues to follow the API engine.

This prevents connections opened by one task loop from being reused by a later
closed/replaced loop. It does not change task schedules, domain transitions,
idempotency, retry/lease semantics, finance guards or delivery capabilities.
Existing outbox and payout safety gaps remain separate release blockers.

## Verify a candidate

In an isolated migrated PostgreSQL/PostGIS environment, run the complete API test
suite with APP_ENV=test. `test_worker_connection_lifecycle.py` verifies separate
PostgreSQL backend connections across event loops, closure of both connections,
and repeated execution of the booking expiry task. The unit tests verify that
worker tracing targets the actual worker engine.

At a separately authorized rollout, drain the old workers before starting the
candidate workers. Monitor worker heartbeat, task failures, connection count and
outbox backlog. NullPool adds a connection setup per session; keep worker
concurrency bounded by the database connection budget. This change is not a
performance certification or authorization to start the scheduler.

## Recovery boundary

No migration or data conversion is needed. Revert the eventual PR squash commit
or restore the previous approved worker image under the release rollback process.
Do not run old and new worker versions against live workloads as a validation
shortcut. Tracing may remain disabled; no telemetry destination or capability is
activated by this change. The architecture inventory remains a dated source
checkpoint; this runbook records the worker lifecycle extension.

## Main refresh validation

After the required APP_ENV validation merged in PR #99, the complete isolated
backend suite passes with 286 tests and eight subtests. Ruff, mypy, migration
drift checks and deterministic OpenAPI equality also pass. Final-head CI and
independent review remain separate merge gates.
