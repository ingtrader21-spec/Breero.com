# Runtime resource lifecycle exact-head CI

This ordinary repository commit follows the deterministic Ruff cleanup and triggers the required quality gate on the completed BE-05, BE-06, and OPS-02 implementation.

The review head must prove all of the following together:

- one bounded Redis connection pool is owned by each FastAPI process;
- rate limiting uses an atomic Redis token bucket and a bounded process-local degraded fallback rather than opening a connection per request;
- PostgreSQL pool size, overflow, acquisition timeout, recycle interval, health checking, and LIFO reuse are explicit settings;
- startup warms PostgreSQL and Redis and starts Keycloak JWKS refresh when enabled;
- shutdown closes Redis and disposes the SQLAlchemy engine;
- readiness reuses the lifespan-owned Redis client;
- the image default command enables proxy headers while trusting only the private proxy network range;
- public-form rate limiting uses the shared limiter and preserves its stable domain error;
- no temporary repair workflow remains in the pull-request diff.

The immediately preceding cleanup commit is `59becb0b8c43c1df076261fb685d582d137f29bb`. Only the required quality result attached to the commit containing this document is final acceptance evidence.
