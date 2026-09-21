# BREERO security

Passwords, reset tokens, refresh tokens, API credentials, and authorization headers must never be logged. Tokens persisted by BREERO are hashed. Production secrets use file bindings and production startup rejects defaults, wildcard CORS, unsafe enabled release flags, shared JWT secrets, and direct Odoo access.

RBAC and object-level checks are server-side. Rate limits cover login, registration, recovery, address/timezone lookup, availability, holds, and booking creation. Hold controls combine hashed IP, booking-session, and account-token signals and cap active holds per owner.

Responses set anti-sniffing, frame denial, strict referrer, and permissions-policy headers. Raw exceptions are not returned. Database changes use Alembic and assignment/capacity mutations use transactions and locking.
