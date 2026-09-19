# Readiness dependency deadline

Milestone 1 / PR #126 gives `/health/ready` one three-second asynchronous timeout
budget for PostgreSQL connection/query and Redis readiness work. This extends the
existing Redis socket timeouts to cover stalled database readiness work as well.
Cooperative cancellation releases the connection context and closes the Redis
client. Driver cancellation/cleanup behavior remains part of runtime validation.

The response contract stays unchanged: healthy dependencies return status ready
and dependency checks; a schema mismatch returns the existing structured 503;
a dependency failure/timeout returns the sanitized 503 `dependency unavailable`.
`/health` and `/health/live` remain liveness endpoints. This PR does not add the
separate `/ready` alias proposed in PR #124.

Current telemetry is preserved: PostgreSQL, schema and Redis readiness metrics
reflect the dependency actually checked. Failure logs include the dependency name
and exception class, never connection strings or raw exception text. This does
not enable tracing or add a metrics destination.

## Validation and operation

Use isolated PostgreSQL/PostGIS and Redis for the full API test suite.
`test_readiness_timeout.py` covers stalled query/ping/acquisition, successful
cleanup, healthy responses, schema mismatch and sanitized diagnostics. Preserve
an ingress/probe timeout that allows the application deadline and driver cleanup
to complete. Readiness failure is a reason to keep the candidate out of routing,
not to bypass the migration or identity gates.

The dependency refresh retained in this PR aligns all four Next.js applications
and eslint-config-next with the existing patched 15.5 release line, keeps current
root overrides and regenerates the frozen lockfile. No frontend contract or
capability is activated. Run the dependency audit, lint, typecheck, unit tests,
contract checker, production builds and existing browser E2E suite before merge.

No schema migration is introduced. Roll back the eventual squash commit or the
approved candidate image under release governance if needed; no data rollback
is required. Restoring an earlier image is not authorization to route an unhealthy
candidate. The architecture inventory remains a dated source checkpoint; this
runbook records the readiness extension.
