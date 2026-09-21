# BREERO observability

HTTP middleware emits structured completion/failure events with request ID, correlation ID, method, path, status, and duration, without request bodies or authorization headers. Health endpoints separate liveness and readiness; readiness verifies PostgreSQL, the exact Alembic head, and Redis.

Domain audit records cover identity, provider onboarding/configuration, booking lifecycle, capacity holds, assignments, feature flags, and operating hours. Operational counters should use the names in the architecture specification (`booking_requests_total`, `holds_created`, `no_capacity_total`, `assignment_total`, and related metrics) and must avoid raw PII labels.
