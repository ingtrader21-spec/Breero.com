# BREERO API

The FastAPI application publishes `/openapi.json` and `/docs`. Routers follow `router → domain service → repository/query → async SQLAlchemy → PostgreSQL`. Public booking endpoints use the `{data, meta, error}` envelope; global domain, validation, authentication, authorization, conflict, and rate-limit errors use the same safe envelope.

Authentication is bearer access plus rotating opaque refresh tokens. Roles are declared through route dependencies and object ownership is rechecked in services. All requests receive `X-Request-ID` and `X-Correlation-ID` response headers.

OpenAPI generation and frontend contract validation run through `apps/api/scripts/generate_openapi.py` and `pnpm contract:check`.
