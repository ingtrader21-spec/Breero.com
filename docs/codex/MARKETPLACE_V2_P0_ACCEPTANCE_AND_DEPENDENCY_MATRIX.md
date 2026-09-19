# BREERO Marketplace V2 — P0 Acceptance and Dependency Matrix

## Purpose

This document is the production acceptance authority for Marketplace V2 P0.

A branch, endpoint, migration, or passing unit test does not by itself make P0 complete. P0 is complete only when every gate in this document has current evidence against the exact candidate head.

Merging this documentation does not authorize deployment, production data changes, capability activation, or marketplace feature work.

## Execution order

```text
PR #38
CI-green API safety/foundation candidate
        ↓
PR #39
Marketplace V2 implementation authority
        ↓
be/marketplace-v2-p0-api-foundation
        ↓
be/marketplace-v2-p0-authentication
        ↓
be/marketplace-v2-p0-authorization
        ↓
be/marketplace-v2-p0-capabilities-idempotency
        ↓
be/marketplace-v2-p0-integration-reliability
        ↓
be/marketplace-v2-p0-storage-uploads
        ↓
be/marketplace-v2-p0-observability-operations
        ↓
P0 PRODUCTION GATE
        ↓
Catalog
```

Every implementation branch must start from the latest merged target after its dependencies are green. Do not create all branches in advance and do not use one permanent integration branch.

## Evidence rules

Every PASS claim must record:

```text
repository
branch
exact commit SHA
target/base SHA
migration head
workflow run IDs
test commands
test counts
review status
unresolved blocking comments
capability-default snapshot
deployment status
```

Evidence is stale when new commits land, the base changes materially, migrations change, security findings change, or a required dependency is rerun at a different head.

No branch may bypass branch protection, required reviews, required checks, or environment approvals.

## P0 dependency matrix

| Gate | Depends on | Unlocks |
| --- | --- | --- |
| API foundation | PR #35 safety baseline and approved authority | Authentication |
| Authentication | API foundation and identity migration | Authorization |
| Authorization | Authentication and identity binding | Protected domain commands |
| Capabilities | API foundation and canonical PR #35 capability service | Safe feature exposure |
| Idempotency/concurrency | Database migration and command context | Reliable mutations |
| Integration reliability | Transactions, audit, idempotency | Safe adapters and callbacks |
| Storage/uploads | Authorization, audit, outbox/workers | Attachments and evidence |
| Observability/operations | All worker and request boundaries | Production diagnostics |
| Database acceptance | Every additive P0 migration | Final P0 gate |
| Final P0 | Every gate PASS at compatible heads | Catalog |

## P0 API foundation

```text
P0_API_FOUNDATION=PASS
```

Required:

- `/api/v2` router is mounted inside the existing FastAPI monorepo.
- The standard V2 error envelope is implemented.
- Command context carries actor, tenant/legal entity, idempotency key, request ID, correlation ID, client address, and user agent where applicable.
- Request and correlation IDs are validated, logged, returned, and propagated.
- OpenAPI is generated and the V2 contract cannot silently become stale.
- Operation IDs are unique and stable.
- Existing `/api/v1` behavior remains compatible.
- No placeholder production endpoint returns fake success.
- No marketplace feature domain is implemented in this gate.

Required evidence:

- API tests for V1/V2 compatibility.
- Error-contract tests for representative 400/401/403/404/409/422/429/5xx behavior.
- OpenAPI generation and drift checks.
- Backend lint, typecheck, tests, migration checks, dependency audit, container build, and vulnerability scan.

## P0 authentication

```text
P0_AUTHENTICATION=PASS
```

Required:

- Production authentication authority is Keycloak/OIDC.
- Canonical issuer is `https://auth.codestra.co/realms/codestra`.
- Human authentication uses Authorization Code with PKCE.
- Machine authentication uses Client Credentials.
- Identity binding uses issuer plus subject, never email.
- `external_identities` has a unique `(issuer, subject)` constraint.
- Signature, issuer, audience, subject, expiration, not-before, issued-at, algorithm, key ID, and authorized party where applicable are validated.
- OIDC discovery and JWKS are cached.
- Unknown `kid` triggers one controlled refresh for key rotation.
- Token validation fails closed after a failed refresh.
- Local production authentication and deterministic JWT-to-user UUID generation are disabled.

Required negative tests:

```text
wrong issuer → denied
wrong audience → denied
expired token → denied
not-yet-valid token → denied
unsupported algorithm → denied
unknown key after refresh → denied
missing subject → denied
disabled/unlinked identity → denied
```

## P0 authorization

```text
P0_AUTHORIZATION=PASS
```

Required:

- Authentication resolves to a stable Principal rather than exposing JWT dictionaries to domain services.
- Permission checks are separate from role membership.
- Customer ownership is enforced.
- Provider membership and provider ownership are enforced.
- Worker assignment is enforced.
- Tenant and legal-entity boundaries are enforced.
- Ops permissions are explicit.
- Admin permissions are explicit.
- Ownership filtering occurs in repository queries whenever practical.
- Sensitive lookup failures do not reveal cross-account resource existence.

Required negative tests:

```text
wrong customer → denied
wrong provider → denied
wrong worker → denied
wrong tenant → denied
wrong legal entity → denied
missing permission → denied
suspended provider mutation → denied
cross-account enumeration → denied
```

## P0 capabilities

```text
P0_CAPABILITIES=PASS
```

Required:

- The canonical capability authority introduced by PR #35 is reused.
- No duplicate capability registry or conflicting V1/V2 projection exists.
- Backend dependencies enforce capabilities at the HTTP boundary.
- Important domain commands enforce capabilities again for internal callers.
- Effective capability requires code availability, release flag, dependency readiness, provider readiness, and environment permission.
- Frontend visibility is never treated as enforcement.
- Disabled capabilities do not expose executable mutations.

The following production capabilities remain disabled unless separately approved:

```text
payments
online checkout
paid leads
payouts
automatic refunds
automatic booking
automatic assignment
automatic confirmation
provider self-service
marketplace matching
marketplace messaging
marketplace reviews
marketing email
marketing SMS
```

## P0 idempotency and concurrency

```text
P0_IDEMPOTENCY=PASS
```

Required:

- Mutating commands use a stable `Idempotency-Key`.
- The idempotency identity includes actor, operation, and key.
- Request payloads are hashed canonically.
- Same key plus same request returns the same business result.
- Same key plus different request returns 409.
- Same key while processing returns a safe conflict/retry response.
- Database uniqueness makes acquisition safe under concurrency.
- Every first acquisition and expired-record recycle receives a fresh generation token; completion, failure, and replay-state mutation require that exact current token.
- A stale owner cannot complete or fail a recycled idempotency generation.
- Important aggregates use optimistic concurrency versions.
- Commands requiring serialization use row locks where appropriate.
- Zero rows updated for an expected version returns `409 CONCURRENT_MODIFICATION`.
- Business mutation, history, audit, idempotency completion, and outbox append commit atomically.

Required real PostgreSQL tests:

```text
simultaneous acquisition → one owner
recycled acquisition → fresh token and stale owner cannot finalize
same request replay → same result
different payload → conflict
worker/process failure → safe recovery
concurrent state transition → one business result
transaction rollback → no partial audit/outbox/idempotency result
```

## P0 integration reliability

```text
P0_INTEGRATION_RELIABILITY=PASS
```

Required outbox behavior:

- Durable transactional outbox.
- `PENDING_CONFIGURATION` state for disabled or unconfigured delivery.
- Recoverable database leases with claim tokens and expirations.
- Stale lease recovery.
- Retryable and terminal failure states.
- Exponential backoff with bounded jitter.
- `delivered_at`, `last_error`, error code, and error timestamp.
- Manual retry is authorized, audited, and idempotent.
- Business state remains committed when Codestra or another adapter is unavailable.

Required inbox behavior:

- Durable webhook inbox before domain processing.
- Cryptographic verification before an event is trusted.
- Timestamp tolerance and replay protection.
- Constant-time signature comparison.
- Provider/event uniqueness for duplicate protection.
- Raw payload hash and safe metadata retention.
- Asynchronous inbox workers rather than inline third-party business processing.
- Recoverable leases, retryable/terminal states, and manual recovery.
- Every inbox claim uses a fresh per-claim token separate from stable worker identity; heartbeat and every finalization require the exact current token.
- A stale translator cannot finalize a newer inbox claim.
- Manual durable-inbox replay requires `integration.replay`; `integration.retry` is insufficient.

Required tests:

```text
duplicate webhook → one business result
invalid signature → denied and not trusted
stale timestamp → denied
replayed delivery → deduplicated
worker crash → safe retry
stale lease → recoverable
adapter unavailable → transaction remains saved
terminal failure → operational exception
```

## P0 storage and uploads

```text
P0_STORAGE=PASS
```

Required:

- Upload sessions are authorized for a specific actor, resource, and purpose.
- File size, declared type, detected type, extension, and count limits are enforced.
- Object storage is private.
- Credentials and identity documents never use permanent public URLs.
- Upload completion verifies object existence, size, checksum, and ownership.
- Malware scanning is mandatory for public/provider uploads.
- Domain consumers can use only `CLEAN` objects.
- Quarantined/rejected objects are inaccessible.
- Download access is temporary, signed, and record-authorized.
- Deletion and retention actions are audited.
- Storage adapters are behind BREERO interfaces rather than embedded vendor SDK calls.

Required tests:

```text
wrong owner upload → denied
oversize upload → denied
type mismatch → denied
malware result → quarantined
non-CLEAN attachment use → denied
expired signed access → denied
cross-tenant download → denied
```

## P0 observability and operations

```text
P0_OBSERVABILITY=PASS
```

Required:

- Structured logs contain request ID and correlation ID.
- Audit and integration records inherit the correlation ID.
- Metrics cover HTTP outcomes/latency, authentication failures, authorization denials, idempotency conflicts, outbox/inbox backlog and age, retries, terminal failures, storage scans, and worker status.
- Workers publish heartbeat and version.
- Operational exceptions are queryable and recoverable without direct SQL access.
- Health endpoints exist:

```text
/health
/health/live
/health/ready
/health/version
```

- Liveness does not depend on external services.
- Readiness validates required dependencies and exact migration compatibility.
- Version reports immutable release identity without exposing secrets.
- Alerts exist for stale workers, growing queues, old messages, terminal failures, dependency failures, and backup failures.

## P0 database acceptance

```text
P0_DATABASE=PASS
```

Required:

- All migrations are additive and use the existing Alembic lineage.
- Current production migration head upgrades to the new head in a disposable copy.
- Empty PostgreSQL/PostGIS database upgrades to head.
- Downgrade/rollback behavior is rehearsed where supported.
- Schema drift check passes.
- All timestamps are timezone-aware.
- Required unique, foreign-key, check, partial, and PostGIS indexes exist.
- PostgreSQL/PostGIS repository, integration, concurrency, and query-plan tests pass.
- No production database is touched during validation.
- Backup and isolated restore rehearsal cover the candidate schema.

## P0 security acceptance

```text
P0_SECURITY=PASS
```

Required:

- Secret scan passes.
- Dependency audit passes.
- Container vulnerability scan has no unapproved HIGH/CRITICAL findings.
- No stack trace, token, credential, raw private document, or internal risk reason is exposed.
- Rate limits exist for authentication, public submission, uploads, and webhook boundaries.
- CORS uses explicit origins.
- Security headers remain enabled.
- Production secrets use mounted/configured secret authorities and are never committed.
- Webhook and adapter credentials are scoped and rotatable.
- Negative authorization and tenant-isolation suites pass.

## P0 final gate

```text
P0_FINAL=PASS
```

Only when all are PASS at mutually compatible exact heads:

```text
P0_API_FOUNDATION
P0_AUTHENTICATION
P0_IDENTITY
P0_AUTHORIZATION
P0_CAPABILITIES
P0_IDEMPOTENCY
P0_CONCURRENCY
P0_AUDIT
P0_INTEGRATION_RELIABILITY
P0_OUTBOX
P0_INBOX
P0_WEBHOOKS
P0_STORAGE
P0_NOTIFICATIONS
P0_OPERATIONS
P0_OBSERVABILITY
P0_DATABASE
P0_SECURITY
P0_DEPLOYABILITY
```

If any required gate is FAIL, BLOCKED, NOT_RUN, stale, or lacks evidence:

```text
P0_FINAL=FAIL
CATALOG_START=DENIED
PRODUCTION_APPROVAL=DENIED
```

A merged documentation PR never satisfies this gate.

## Branch ownership boundaries

Backend branches may change:

```text
apps/api/**
apps/api/migrations/**
backend tests
OpenAPI
backend workflow checks when required
```

Frontend branches may change:

```text
apps/web/**
apps/partner/**
apps/ops/**
apps/admin/**
packages/ui/**
packages/api-client/**
packages/types/**
frontend tests
```

Expected cross-boundary overlap is limited to `packages/types` and `packages/api-client` after a backend contract is stable and its OpenAPI artifact is green.

## Post-P0 feature order

After `P0_FINAL=PASS`:

```text
Catalog
  ↓
ProjectRequest
  ↓
Provider Core
  ↓
Credentials + Availability
  ↓
Matching
  ↓
Opportunities
  ↓
LeadConnection
  ↓
Quotes
  ↓
Messaging
  ↓
Booking Bridge
  ↓
Jobs
  ↓
Reviews
  ↓
Notifications
  ↓
Disputes
  ↓
Ops/Admin
  ↓
Frontend portals and forms
```

Payments, payouts, paid leads, and subscriptions remain separate later approvals.
