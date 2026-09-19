# BREERO Marketplace V2 — P0 Production Hardening Specification

## Status

This document is binding implementation guidance for the Marketplace V2 P0 production foundation. It does not declare any P0 gate complete, enable a capability, approve a merge, or authorize deployment.

The reviewed system is **architecturally complete enough to implement, but still P0-NO-GO for Marketplace V2**. The next work should be a focused production-hardening program, not more feature design.

## Production hardening backlog

| Area | Current problem | Required production fix | Done when |
| --------------------------------------------------- | ------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| `/api/v2` foundation                                | Only one V2 endpoint exists                                         | Mount complete V2 router structure, standard errors, request/correlation context, OpenAPI | V2 foundation tests green, V1 unaffected                          |
| Authentication                                      | Local auth still active, Keycloak optional, email identity matching | Mandatory production OIDC, immutable `(issuer, subject)` binding, JWKS cache/rotation     | Invalid issuer/audience/token denied; local prod auth unavailable |
| Authorization                                       | Scattered V1 checks                                                 | Reusable Principal + permissions + record policies                                        | Cross-customer/provider/worker tests all deny                     |
| Capabilities                                        | Projection exists but commands aren't fully guarded                 | Capability checks at API + domain-command layer                                           | Disabled feature impossible to execute                            |
| Idempotency                                         | Domain-specific only                                                | Generic transactional idempotency service                                                 | Duplicate concurrent commands produce one business effect         |
| Concurrency                                         | Inconsistent                                                        | Standard aggregate `version` / `If-Match` behavior                                        | Stale writes produce 409/412                                      |
| Error contract                                      | V2 handler incomplete                                               | Preserve security headers, 401/429 headers, handle uncaught failures, frontend parsing    | Every V2 error uses one documented contract                       |
| Outbox                                              | Good foundation but claim/finalization gaps                         | Claim-token validation, heartbeat, destination registry, canonical events                 | Stale worker cannot finalize; unknown event cannot disappear      |
| Inbox/webhooks                                      | Missing generic processing                                          | Durable inbox, signature/replay validation, async processing                              | Duplicate webhook produces one effect                             |
| Storage                                             | Missing                                                             | Private object storage, scan/quarantine/signed downloads                                  | No unsafe attachment can reach domain                             |
| Audit                                               | Missing context                                                     | Add tenant/legal entity/IP/user-agent/correlation                                         | All sensitive commands traceable                                  |
| Observability                                       | Partial                                                             | Health/version, metrics, traces, worker heartbeat, queue age                              | Alerts can detect actual platform failures                        |
| Deployment | Missing V2 wiring | Keycloak/middleware secrets, gateway route, internal-route denial | Staging deployment is gated and reproducible |
| Backup/restore                                      | Not yet proved                                                      | Automated backup + isolated restore rehearsal                                             | Restore passes against current migration head                     |

---

# P0 implementation branches

Do these in this exact order:

```
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
be/marketplace-v2-p0-storage
        ↓
be/marketplace-v2-p0-observability-deployment
        ↓
──────── P0_FINAL GATE ────────
        ↓
Catalog
```

Do not start Catalog before `P0_FINAL=PASS`.

---

# P0-01 — API foundation corrections

This PR should own only common V2 transport infrastructure.

Implement:

```
apps/api/app/api/v2/
    router.py
    errors.py
    dependencies.py
    context.py
```

The standard error shape should be:

```
{
  "code": "QUOTE_EXPIRED",
  "message": "The quote has expired.",
  "correlation_id": "7e92...",
  "fields": null
}
```

The global V2 exception stack must cover:

```
DomainError
RequestValidationError
HTTPException
rate-limit errors
dependency-unavailable errors
unexpected exceptions
```

Preserve headers such as:

```
WWW-Authenticate
Retry-After
```

An unexpected exception should return a redacted envelope:

```
{
  "code": "INTERNAL_ERROR",
  "message": "The request could not be completed.",
  "correlation_id": "...",
  "fields": null
}
```

Never leak stack traces.

### Real CommandContext

Create it from every request:

```
@dataclass(frozen=True)
class CommandContext:
    request_id: str
    correlation_id: str

    actor_id: UUID | None

    tenant_id: UUID | None
    legal_entity_id: UUID | None

    idempotency_key: str | None

    ip_address: str | None
    user_agent: str | None
```

The same correlation ID must flow into:

```
audit
outbox
inbox
provider adapter calls
logs
```

### API-foundation acceptance

```
V1 OpenAPI unchanged except explicitly approved compatibility work

V2 error envelope works for:
400
401
403
404
409
412
422
429
500
503

401 preserves WWW-Authenticate

429 preserves Retry-After

request ID always exists

correlation ID always exists

OpenAPI generation green

frontend contract test updated
```

---

# P0-02 — Production authentication

This is a blocker before any real V2 user endpoint.

Production must use:

```
Keycloak / OIDC
```

Production startup validation:

```
APP_ENV=production
requires production OIDC enabled
```

Reject startup if production attempts to use local JWT/password authentication.

### Disable local auth in production

In production OIDC mode, these must not issue local identity:

```
local login
local register
local refresh token
local password reset
local JWT issuance
```

They can remain available only in explicitly permitted development/test modes if the project needs them.

### Identity mapping

Add:

```
external_identities
```

Conceptual schema:

```
id UUID PK

user_id UUID FK

issuer VARCHAR NOT NULL
subject VARCHAR NOT NULL

email_at_link_time VARCHAR NULL

created_at TIMESTAMPTZ
last_seen_at TIMESTAMPTZ

UNIQUE(issuer, subject)
```

Never use email as the production identity key.

Flow:

```
OIDC token
   ↓
verify
   ↓
(issuer, subject)
   ↓
external_identity
   ↓
local user
   ↓
memberships / permissions
```

### JWT verification

Validate:

```
signature
iss
aud
azp where required
exp
nbf
iat
sub
algorithm
kid
```

The canonical production issuer from your design must be explicitly enforced.

### JWKS

Use a process-wide cached JWKS/discovery manager.

Behavior:

```
known kid
→ use cache

unknown kid
→ refresh JWKS once
→ retry

still unknown
→ reject
```

Do not create a fresh JWK client for every API call.

### Production auth negative tests

```
wrong issuer → 401

legacy issuer → 401

wrong audience → 401

expired token → 401

not-before violation → 401

unknown kid after refresh → 401

malformed JWT → 401

missing token → 401
```

---

# P0-03 — Record-level authorization

Create:

```
domains/authorization/
    principal.py
    permissions.py
    policies.py
    dependencies.py
```

A Principal should represent effective application identity:

```
@dataclass(frozen=True)
class Principal:
    user_id: UUID

    roles: frozenset[str]
    permissions: frozenset[str]

    provider_ids: frozenset[UUID]

    worker_id: UUID | None

    tenant_id: UUID | None
    legal_entity_ids: frozenset[UUID]
```

### Authorization formula

Every protected operation requires:

```
authenticated
AND
permission
AND
tenant/legal-entity access
AND
record ownership/membership
AND
resource state permits action
```

### Customer

Customer-resource SQL queries include customer ownership.

Example:

```
WHERE project_request.id = :request_id
AND project_request.customer_id = :customer_id
```

Prefer this over loading arbitrary IDs first.

### Provider

Provider-resource queries include an active provider membership.

```
provider member ACTIVE
AND
resource.provider_id belongs to membership
```

### Worker

Worker sees only:

```
authorized provider
AND
assigned worker
AND
permitted job state
```

### Mandatory negative authorization suite

```
Customer A cannot access Customer B ProjectRequest

Customer A cannot access Customer B Quote

Customer A cannot access Customer B Conversation

Provider A cannot access Provider B Opportunity

Provider A cannot access Provider B LeadConnection

Provider A cannot access Provider B Quote

Provider A cannot access Provider B Conversation

Provider A cannot access Provider B Customer

Provider A cannot access Provider B Job

Worker cannot access unassigned Job

Dispatcher cannot approve payout

Customer Support cannot verify credentials
```

---

# P0-04 — Capability enforcement

The current public capability projection should remain the **single authority**.

Do not build a second unrelated capability registry.

Each command needs:

```
route exists
AND
capability effective
AND
principal authorized
AND
record authorized
AND
provider/entity ready
AND
valid state transition
```

Example:

```
@router.post(
    "/{quote_id}/accept",
    dependencies=[
        Depends(require_capability("quotes")),
        Depends(require_permission("quote.accept")),
    ],
)
```

Then `QuoteService.accept()` validates the capability again for non-HTTP/internal calls.

Dangerous capabilities remain false:

```
marketplace_matching
provider_self_service
quotes
messaging
reviews
instant_booking
automatic_assignment
payments
payouts
marketing
```

until separately activated.

---

# P0-05 — Generic idempotency

Add:

```
idempotency_records
```

Fields:

```
id UUID PK

actor_key
operation
idempotency_key

request_hash

status

resource_type
resource_id

response_code
response_json

created_at
updated_at
expires_at
```

Unique:

```
(actor_key, operation, idempotency_key)
```

States:

```
IN_PROGRESS
COMPLETED
FAILED_RETRYABLE
```

### Semantics

```
new key
→ acquire

same key + same payload + completed
→ return original result

same key + different payload
→ 409 IDEMPOTENCY_KEY_REUSED

same key currently executing
→ 409/425 REQUEST_IN_PROGRESS
```

### Commands requiring idempotency

```
ProjectRequest submit

Provider application submit

Opportunity accept/decline

Quote send
Quote revise
Quote accept/decline

Booking confirm/cancel

Job assign/reassign
Job transition
Job complete

Review submit

Dispute create

Integration retry

Payments/refunds/payouts later
```

### Atomic transaction

Critical rule:

```
business mutation
+
history
+
audit
+
outbox
+
idempotency completion
=
same DB transaction
```

---

# Optimistic concurrency

Standardize aggregate versions.

Use version on:

```
ProjectRequest
Provider
Opportunity
Quote
Booking
Job
```

For update endpoints support either:

```
If-Match
```

or an explicit version field, preferably `If-Match` for REST resources.

Example:

```
If-Match: "17"
```

Stale version:

```
412 PRECONDITION_FAILED
```

For domain-command conflicts where ETag semantics are not applicable:

```
409 CONCURRENT_MODIFICATION
```

---

# P0-06 — Durable webhook inbox

Create generic:

```
integration_inbox
```

Fields should include:

```
id

provider
external_event_id

event_type
schema_version

request_hash

signature_verified
signature_key_id

received_at
verified_at
processing_started_at
processed_at

status

attempt_count
max_attempts

next_attempt_at

lease_owner
lease_expires_at

last_error_code
last_error_message_redacted

correlation_id

payload
```

Unique:

```
(provider, external_event_id)
```

### States

```
RECEIVED
VERIFIED
PROCESSING
RETRYABLE
PROCESSED
FAILED_TERMINAL
REJECTED
```

### Webhook path

```
raw body
   ↓
max-size check
   ↓
signature/auth verification
   ↓
timestamp
   ↓
event/replay identifier
   ↓
request hash
   ↓
durable inbox insert
   ↓
202
   ↓
worker
   ↓
translator
   ↓
authorized domain command
```

Business mutations must not happen synchronously inside the external webhook request.

---

# Inbound provider contracts

Define contracts now for:

```
middleware callbacks

email:
delivered
bounce
complaint
suppression

SMS:
sent
delivered
failed
reply where supported

malware:
scan completed

Stripe later:
payment success/failure
refund
account status
payout
```

---

# Manual webhook replay

Ops endpoint:

```
POST /api/v2/ops/integration-inbox/{id}/replay
```

Requires:

```
integration.replay
```

and:

```
audit
reason
correlation ID
```

Do not mutate/delete the old record to replay it.

---

# P0-07 — Outbox hardening

Keep the existing outbox and fix its remaining correctness problems.

### Claim ownership

When claiming an event generate:

```
claim_token
lease_expires_at
```

When finalizing:

```
UPDATE integration_event
SET status = ...
WHERE id = :id
AND claim_token = :claim_token
AND status = 'PROCESSING'
```

If zero rows update:

```
worker lost ownership
→ do not finalize
```

This prevents a stale worker from reporting successful delivery after another worker reclaimed the event.

### Lease heartbeat

For potentially long provider calls:

```
processing
→ periodically extend lease
```

or choose a lease duration greater than the strictly bounded provider timeout.

### Unknown event type

Never:

```
unknown event
→ DELIVERED
```

Instead:

```
FAILED_TERMINAL
code=UNROUTABLE_EVENT
```

and surface to Ops.

### Event registry

Create one registry:

```
EVENT_ROUTES = {
    "project_request.submitted.v1": [...],
    "provider_application.submitted.v1": [...],
    "quote.sent.v1": [...],
    "job.completed.v1": [...],
}
```

New integration events must follow:

```
domain.action.v1
```

Legacy event names may need compatibility translation; do not silently rename historical events.

### Delivery semantics

Separate:

```
processed_at
```

from:

```
delivered_at
```

A terminal failure is processed, not delivered.

---

# Canonical audit fields

Expand audit to contain:

```
actor

action

resource type
resource ID

tenant
legal entity

correlation ID

request ID

IP
user agent

safe metadata

created at
```

No secrets.

---

# P0-08 — Storage and uploads

This is mandatory before Marketplace V2 attachments.

Add:

```
storage_objects
upload_sessions
```

### Storage object

```
id

owner user
provider where applicable

purpose

storage key

original filename
content type
size
sha256

status

created at
deleted at
```

Purposes:

```
PROJECT_ATTACHMENT

PROVIDER_CREDENTIAL

PROVIDER_GALLERY

MESSAGE_ATTACHMENT

JOB_EVIDENCE

DISPUTE_EVIDENCE
```

States:

```
PENDING_UPLOAD
UPLOADED
SCANNING
CLEAN
QUARANTINED
REJECTED
DELETED
```

### API

```
POST /api/v2/uploads

POST /api/v2/uploads/{id}/complete

GET /api/v2/uploads/{id}

DELETE /api/v2/uploads/{id}
```

Private downloads need short-lived authorized access.

---

# File validation

Require:

```
maximum total bytes

per-purpose MIME allowlist

extension/MIME consistency

checksum

malware scan

private bucket

no executable content

no permanent public URL
```

Credential files should have stricter access and retention than customer job photos.

---

# Malware scanning

Flow:

```
UPLOADED
 ↓
SCANNING
 ↓
CLEAN
```

or:

```
SCANNING
 ↓
QUARANTINED
```

No domain can attach an object until:

```
status == CLEAN
```

---

# Cleanup

Scheduler cleans:

```
abandoned upload sessions

never-completed uploads

rejected/quarantined files according to policy

expired signed-download metadata
```

---

# P0-09 — Observability

Add:

```
/health/live
/health/ready
/health/version
```

Version should report safe build metadata:

```
{
  "version": "...",
  "git_sha": "...",
  "image_digest": "...",
  "migration_head": "..."
}
```

Do not report credentials/config secrets.

### Readiness

Verify:

```
PostgreSQL reachable

expected migration head

PostGIS extension available

required worker dependencies where applicable
```

Do not fail readiness merely because a disabled optional provider is unavailable.

---

# Metrics

Add at minimum:

```
HTTP request count

HTTP latency

HTTP 4xx/5xx

database latency

DB pool utilization

worker heartbeat

outbox:
pending count
oldest pending age
retryable count
terminal count

inbox:
pending count
oldest pending age
retryable count
terminal count

upload:
scanning backlog
quarantine count

webhook:
verification failures
duplicates

authentication failures

authorization denials
```

Later marketplace metrics:

```
matching duration

zero-result matches

opportunity response time

quote conversion

job completion
```

---

# Tracing

Use OpenTelemetry or an equivalent trace system.

Propagate:

```
trace ID

request ID

correlation ID
```

through:

```
HTTP
database
workers
outbox
provider adapters
```

---

# P0-10 — Deployment/security

Production Compose/deployment configuration must contain all required OIDC and middleware configuration.

Add safe examples to `.env.example`:

```
AUTH_MODE

KEYCLOAK_ENABLED
KEYCLOAK_ISSUER
KEYCLOAK_AUDIENCE

MIDDLEWARE_ENABLED
MIDDLEWARE_URL

secret-file paths
mTLS paths

storage configuration

scan provider configuration
```

Never include real values.

### Gateway

Explicitly route:

```
/api/v2/*
```

and webhook routes that are intended to be public.

Explicitly deny:

```
/internal/**
```

from public ingress.

Internal metrics should not be public.

---

# Backup / restore

Automate:

```
database backup

checksum

off-host encrypted copy

retention

backup failure alert
```

Then prove:

```
backup
→ isolated DB
→ restore
→ migration-head verification
→ API boot
→ smoke tests
```

A backup without a restore rehearsal is not a production-ready backup system.

---

# Database migration rehearsal

For every P0 schema PR prove both:

```
empty database → head
```

and:

```
exact current production migration → head
```

Also:

```
PostGIS enabled

constraints

unique indexes

rollback compatibility where practical

schema drift check
```

No production DB is touched by CI.

---

# Realtime decision

For first Marketplace V2 launch I recommend:

```
polling-first
```

because it reduces production complexity while matching, messaging, notification and job systems stabilize.

Use efficient endpoints with:

```
updated_since

cursor

ETag
```

for polling.

A reasonable cadence:

```
messages       3–5s when open
job status     10–15s
opportunities  15–30s
notifications  30s
```

Later introduce authenticated SSE/WebSocket if product demand justifies it.

If realtime is later added, define:

```
connection auth

resource subscriptions

participant authorization

sequence cursor

resume/replay

heartbeat

backpressure

token expiration

revocation
```

before implementation.

---

# Frontend production corrections

The frontend stays on its existing Next.js/React architecture.

Do not rewrite to Vue.

The first frontend branch after backend P0 should be:

```
fe/marketplace-v2-p0-api-auth
```

Its responsibilities:

```
typed V2 DTOs

V2 error envelope parsing

authentication architecture

capability consumption

stable Idempotency-Key support

409/412 handling

429 Retry-After

503 handling
```

---

# Token architecture decision

The current `sessionStorage` token design should not be considered the final production solution.

My preferred production architecture is:

```
Browser
   ↓
Next.js BFF/session
   ↓
Secure HttpOnly SameSite cookie
   ↓
OIDC tokens kept server-side / protected session
   ↓
FastAPI
```

This reduces exposure of refresh/access tokens to JavaScript.

If bearer tokens remain in the browser, that must be a deliberate documented security decision with appropriate CSP/XSS protections.

Do not leave the decision implicit.

---

# Frontend API generation

Stop manually maintaining the entire V2 client once V2 becomes large.

Preferred:

```
FastAPI/Pydantic
 ↓
OpenAPI
 ↓
generated TypeScript API types/client
 ↓
thin application wrapper
 ↓
UI
```

CI checks that generated code is not stale.

---

# Required endpoint annex

Add a binding endpoint registry to the implementation authority.

Every endpoint gets one row with:

| Field | Required |
| --------------------------- | ------------- |
| Method                      | Yes           |
| Path                        | Yes           |
| Operation ID                | Yes           |
| Request DTO                 | Yes           |
| Response DTO                | Yes           |
| Principal                   | Yes           |
| Permission                  | Yes           |
| Record predicate            | Yes           |
| Capability                  | Yes           |
| Idempotency                 | Yes           |
| `If-Match`/version          | Yes           |
| State transition            | If mutation   |
| Audit action                | If applicable |
| Outbox event                | If applicable |
| Rate limit                  | Yes           |
| PII response classification | Yes           |
| Error contract              | Yes           |

Example:

```
Operation:
acceptQuote

POST
/api/v2/quotes/{quote_id}/accept

Principal:
CUSTOMER

Permission:
quote.accept

Record:
quote.request.customer_id == principal.user_id

Capability:
quotes

Idempotency:
required

If-Match:
required

From:
SENT

To:
ACCEPTED

Audit:
QUOTE_ACCEPTED

Event:
quote.accepted.v1

Rate:
10/min/customer

PII:
provider public profile only

Errors:
401
404
409
412
422
429
503
```

Do this for all 143 contracts before declaring the V2 API specification binding.

---

# Required webhook annex

Every webhook gets:

| Field | Required |
| --------------------- | ------------- |
| Provider              | Yes           |
| Route                 | Yes           |
| Authentication        | Yes           |
| Signature algorithm   | If applicable |
| Signature headers     | Yes           |
| Key rotation          | Yes           |
| Timestamp tolerance   | Yes           |
| Replay ID             | Yes           |
| Maximum body size     | Yes           |
| Inbox uniqueness      | Yes           |
| ACK status/deadline   | Yes           |
| Ordering guarantee    | Yes           |
| Retry policy          | Yes           |
| Terminal policy       | Yes           |
| Event→command mapping | Yes           |
| Retention             | Yes           |
| Redaction             | Yes           |
| Replay permission     | Yes           |

Example:

```
Provider:
Email delivery

Route:
/webhooks/v1/email

Authentication:
mTLS + signed request

Replay key:
provider + event_id

Timestamp tolerance:
300 seconds

Max body:
256 KiB

ACK:
202 after durable inbox commit

Processing:
asynchronous

Retry:
bounded exponential backoff

Terminal:
FAILED_TERMINAL + Ops exception

Retention:
policy-defined

Manual replay:
integration.replay permission; `integration.retry` does not grant durable-inbox replay
```

---

# What remains after P0

Only after all P0 gates pass should these begin:

```
Catalog

ProjectRequest

Provider Core

Provider Credentials

Provider Availability

Matching

Opportunities

LeadConnection

Quotes

Messaging

Booking Bridge

Jobs

Reviews

Notifications

Disputes

Ops

Admin
```

Then frontend feature implementations follow their backend contracts.

---

# Final Marketplace V2 production E2E

Eventually this must pass against the staged production candidate:

```
OIDC login
  ↓
Customer ProjectRequest
  ↓
questionnaire
  ↓
safe upload
  ↓
submit idempotently
  ↓
qualification
  ↓
matching
  ↓
provider opportunities
  ↓
provider accepts
  ↓
LeadConnection
  ↓
conversation
  ↓
versioned quote
  ↓
customer accepts
  ↓
booking
  ↓
worker assignment
  ↓
job
  ↓
completion
  ↓
verified review
```

And all of these failure paths:

```
wrong issuer rejected

wrong audience rejected

Customer A → Customer B denied

Provider A → Provider B denied

Worker A → unassigned job denied

disabled capability denied

expired credential cannot match

suspended provider cannot match

duplicate submit → one result

duplicate opportunity accept → one LeadConnection

duplicate quote accept → one Booking

duplicate webhook → one effect

stale outbox worker cannot finalize

worker crash → lease recovered

middleware unavailable → business transaction survives

unsafe file → quarantined

payment endpoints remain unavailable
```

---

## Final status model

At the state you described:

```
REQUEST_ONLY_V1=NEAR_PRODUCTION
MARKETPLACE_V2=NO_GO

P0_API_FOUNDATION=FAIL
P0_AUTHENTICATION=FAIL
P0_AUTHORIZATION=FAIL
P0_CAPABILITIES=PARTIAL
P0_IDEMPOTENCY=FAIL
P0_INBOX=FAIL
P0_OUTBOX=PARTIAL
P0_STORAGE=FAIL
P0_OBSERVABILITY=FAIL
P0_DEPLOYMENT=FAIL
P0_FINAL=FAIL
```

The good news is that most of the difficult **architecture decisions are already made**. The remaining P0 work is concrete engineering: authentication, record security, command safety, durable integration processing, storage, and production operations. Once those are actually green, the Marketplace domains can be implemented on top of a foundation that won't need to be rewritten for security or reliability later.

Each step should be delivered as an independently reviewable PR with:

Each step should be delivered as an independently reviewable PR with:

-  a narrowly defined scope and explicit non-goals;
-  architecture/domain changes documented before implementation;
-  additive database migrations where schema changes are required;
-  migration validation from the current production head to the new head;
-  domain services, policies, state machines, commands, repositories, and events kept separate from transport code;
-  thin API routes with documented request/response DTOs;
-  OpenAPI updated and checked for drift;
-  authentication and permission requirements documented for every protected endpoint;
-  record-level authorization tests, including negative cross-customer, cross-provider, cross-worker, and cross-tenant cases;
-  required capability gates enforced server-side;
-  idempotency behavior for every retryable mutation;
-  optimistic-concurrency or `If-Match` behavior for mutable aggregates where needed;
-  state-transition tests for every affected lifecycle;
-  audit events containing actor, resource, request/correlation ID, tenant/legal-entity context, and safe metadata;
-  transactional outbox events for externally relevant business changes;
-  inbox/webhook tests when inbound integrations are involved;
-  provider-adapter contract tests for external systems;
-  retry, timeout, duplicate, replay, stale-lease, and terminal-failure coverage where applicable;
-  PostgreSQL integration tests using the real database engine, plus PostGIS tests for geographic logic;
-  no SQLite substitution for Postgres-specific behavior;
-  frontend typed-contract updates only after the backend contract is stable;
-  frontend form tests for `401`, `403`, `404`, `409`, `412`, `422`, `429`, `500/503`, timeout, retry, and double-submit behavior;
-  accessibility, responsive, and browser E2E coverage for user-facing changes;
-  structured logging and metrics for new critical flows;
-  no credentials, tokens, certificates, local `.env` files, database dumps, or secrets committed;
-  dangerous capabilities left disabled by default;
-  rollback notes, migration compatibility notes, and operational-recovery notes;
-  an exact final commit SHA and evidence that all checks were run on that exact head;
-  independent review with no unresolved blocking threads before merge;
-  no deployment merely because a PR is merged.

Each PR description should end with a compact evidence block like:

```
SCOPE=
BASE_SHA=
FINAL_SHA=

MIGRATION_PREVIOUS_HEAD=
MIGRATION_NEW_HEAD=
MIGRATION_STATUS=

DOMAIN_TESTS=
POSTGRES_TESTS=
POSTGIS_TESTS=
AUTH_TESTS=
NEGATIVE_AUTH_TESTS=
IDEMPOTENCY_TESTS=
CONCURRENCY_TESTS=
OUTBOX_TESTS=
INBOX_WEBHOOK_TESTS=

OPENAPI_STATUS=
TYPECHECK_STATUS=
FRONTEND_TESTS=
PLAYWRIGHT_STATUS=
ACCESSIBILITY_STATUS=

CAPABILITIES_ENABLED=
SECRETS_EXPOSED=NO
PRODUCTION_DB_TOUCHED=NO

KNOWN_RISKS=
ROLLBACK=
BLOCKERS=
NEXT_SAFE_ACTION=
```

That makes every step independently auditable and keeps “code exists,” “tests pass,” “reviewed,” “merged,” and “production-enabled” as separate gates.
