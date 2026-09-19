# BREERO Marketplace V2

## Production Completion Blueprint

## 1. Purpose

This document is the binding implementation authority for taking the existing request-only platform to a production-ready Marketplace V2.

It covers:

```text
architecture
backend
frontend
database
authentication
authorization
capabilities
idempotency
concurrency
audit
APIs
webhooks
outbox
inbox
storage
workers
adapters
CRM/middleware
notifications
operations
security
observability
backups
staging
deployment
rollback
production activation

```

The objective is not merely to make code compile.

The objective is:

```text
PRODUCTION_READY=YES

```

only after every required production gate passes.

## Authority and precedence

This document is the canonical Marketplace V2 production-completion authority.

Supporting documents in this PR remain binding within their scopes:

1. `MARKETPLACE_V2_P0_ACCEPTANCE_AND_DEPENDENCY_MATRIX.md` defines required gate evidence.
2. `MARKETPLACE_V2_CORE_MARKETPLACE_IMPLEMENTATION.md` defines detailed domain and endpoint behavior.
3. `MARKETPLACE_V2_P0_IMPLEMENTATION_SET.md` defines P0 workstream scope.
4. `MARKETPLACE_V2_PRODUCTION_HARDENING_SPEC.md` records the repository-specific hardening findings.

If supporting documents conflict, this completion blueprint controls sequencing, safety and production-readiness decisions. A newer approved ADR may override one explicit decision without weakening unrelated gates.

---

# 2. Current Status

Current state:

```text
REQUEST_ONLY_V1=PARTIAL

MARKETPLACE_V2=NO_GO

PRODUCTION_READY=NO

```

Existing strengths:

```text
FastAPI backend

Next.js / React frontend

PostgreSQL

PostGIS

Redis

Celery/background workers

V1 compatibility

/api/v2 mount must be verified at the accepted source SHA; historical bootstrap inventories are not proof of implementation

request IDs

correlation IDs

domain primitives

PostgreSQL CI

PostGIS CI

outbox foundation

SKIP LOCKED

lease-based processing

production capability defaults disabled

private production database networks

backend security scanning

frontend build/browser testing

```

These should be preserved.

Do not rewrite working foundations simply because Marketplace V2 is being introduced.

---

# 3. Current Critical Gaps

Production blockers are:

```text
Authentication

External identity binding

Record-level authorization

Capability enforcement

Generic idempotency

Standard concurrency

Complete audit context

Outbox ownership correctness

Durable inbox/webhooks

Private storage/uploads

Malware scanning

Notification policy

Operational exceptions

Frontend V2 contract

OIDC browser/session architecture

Observability

Backup/restore evidence

Staging V2 E2E

Immutable release pipeline

Production rollback evidence

```

Marketplace feature implementation must not bypass these.

---

# 4. Final Architecture

```text
                    USERS
                      │
      ┌───────────────┼─────────────────┐
      │               │                 │
   Customer        Provider          Staff
      │               │                 │
      ▼               ▼                 ▼
 apps/web       apps/partner      ops / admin
      │               │                 │
      └───────────────┼─────────────────┘
                      │
                      ▼
                 HTTPS / API
                      │
                      ▼
                 FastAPI API
                      │
                      ▼
               Command Layer
                      │
                      ▼
              Domain Services
                      │
      ┌───────────────┼────────────────┐
      ▼               ▼                ▼
 Authorization      Policy        State Machine
      │               │                │
      └───────────────┼────────────────┘
                      ▼
                 Repository
                      │
                      ▼
             PostgreSQL/PostGIS
                      │
       ┌──────────────┼────────────────────┐
       ▼              ▼                    ▼
     Audit        Idempotency            Outbox
                                             │
                                             ▼
                                          Workers
                                             │
                                             ▼
                                         Adapters
                                             │
                                      Control Plane
                                             │
                    ┌────────────────────────┼─────────────┐
                    ▼                        ▼             ▼
                   CRM                     Email          SMS
                   Odoo                    Klyrow         Telnexa
                                             │
                                          Workflows
                                             │
                                            n8n


External Systems
      │
      ▼
Webhook Endpoints
      │
      ▼
Verify / Authenticate
      │
      ▼
Durable Inbox
      │
      ▼
Inbox Worker
      │
      ▼
Authorized Domain Command

```

---

# 5. System Ownership Rules

## BREERO backend owns

```text
customers

providers

workers

service catalog

ProjectRequests

qualification

matching

opportunities

LeadConnections

quotes

conversations

bookings

jobs

reviews

credentials

availability

disputes

notifications

payments later

payouts later

```

## PostgreSQL owns

Authoritative transactional state.

## PostGIS owns

Authoritative geographic logic.

## Redis owns

Derived/disposable state only.

## Odoo owns

```text
campaign CRM

agent activities

follow-ups

CRM stages

agent notes

campaign operations

CRM projections

```

Odoo must not own marketplace lifecycle state.

## Middleware/control plane owns

```text
integration routing

provider authentication

service orchestration

tenant routing

external API policy

```

It does not own marketplace state.

---

# 6. P0 Production Gate

Marketplace implementation begins only after:

```text
P0_API_FOUNDATION=PASS

P0_AUTHENTICATION=PASS

P0_IDENTITY=PASS

P0_AUTHORIZATION=PASS

P0_CAPABILITIES=PASS

P0_IDEMPOTENCY=PASS

P0_CONCURRENCY=PASS

P0_AUDIT=PASS

P0_INTEGRATION_RELIABILITY=PASS

P0_OUTBOX=PASS

P0_INBOX=PASS

P0_WEBHOOKS=PASS

P0_STORAGE=PASS

P0_NOTIFICATIONS=PASS

P0_OPERATIONS=PASS

P0_OBSERVABILITY=PASS

P0_DATABASE=PASS

P0_SECURITY=PASS

P0_DEPLOYABILITY=PASS

P0_FINAL=PASS

```

---

# 7. P0-01 — API Foundation

Complete the V2 API foundation before feature endpoints.

Required:

```text
/api/v2 router

V2 error envelope

request context

correlation context

CommandContext dependency

OpenAPI operation IDs

ETag / If-Match convention

rate-limit headers

unexpected-exception handling

```

Standard error:

```json
{
  "code": "CONCURRENT_MODIFICATION",
  "message": "The resource changed before this request was completed.",
  "correlation_id": "c-123",
  "fields": null
}

```

Required statuses:

```text
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

```

Must preserve:

```text
WWW-Authenticate

Retry-After

ETag

```

---

# 8. CommandContext

Build a real context for every mutation:

```text
request_id

correlation_id

actor_id

issuer

subject

tenant_id

legal_entity_id

provider_id where applicable

worker_id where applicable

idempotency_key

ip_address

user_agent

```

This context flows into:

```text
authorization

audit

outbox

integration calls

logs

traces

```

---

# 9. P0-02 — Authentication

Production identity must be OIDC-based.

Canonical production issuer:

```text
https://auth.codestra.co/realms/codestra
```

The legacy `auth.codestra.agency` issuer and every other issuer mismatch must be rejected. Configuration examples, deployments, frontend clients, backend validation and tests must use the canonical issuer consistently.

Production rules:

```text
AUTH_MODE=OIDC

local login disabled

local registration disabled

local refresh disabled

local password reset disabled

local JWT issuance disabled

```

Development/test may retain explicit local-auth mode.

Production must fail startup if authoritative OIDC is not configured.

---

# 10. Keycloak/OIDC Validation

Validate:

```text
signature

issuer

audience

authorized party where required

expiration

not-before

issued-at

subject

key ID

algorithm

```

JWKS handling:

```text
process-wide cache

unknown kid
→ refresh discovery/JWKS once
→ retry validation

still unknown
→ reject

```

Do not instantiate a new JWK client for every token.

---

# 11. External Identity

Add:

```text
external_identities

```

Schema:

```text
id UUID PK

user_id UUID FK

issuer VARCHAR NOT NULL

subject VARCHAR NOT NULL

email_at_link_time VARCHAR NULL

created_at TIMESTAMPTZ

last_seen_at TIMESTAMPTZ

UNIQUE(issuer, subject)

```

Authentication flow:

```text
OIDC token

→ validate

→ issuer + subject

→ external identity

→ local user

→ memberships

→ permissions

→ Principal

```

Never use email as identity authority.

---

# 12. P0-03 — Principal and Authorization

Create:

```text
Principal
PermissionRegistry
RecordPolicies
AuthorizationDependencies
AuthorizedRepositories

```

Principal:

```text
user_id

issuer
subject

roles

permissions

provider_ids

worker_id

tenant_id

legal_entity_ids

```

Authorization:

```text
authenticated
AND
permission
AND
tenant
AND
legal entity
AND
record ownership/membership
AND
state permits action

```

---

# 13. Record-Level Security

Preferred pattern:

```text
quote_for_customer(
    quote_id,
    customer_id
)

```

or:

```text
opportunity_for_provider(
    opportunity_id,
    provider_ids
)

```

not:

```text
load arbitrary ID
then discover later
that actor should never have seen it

```

Use `404` where appropriate to avoid cross-tenant resource discovery.

---

# 14. Required Permissions

At minimum:

```text
project_request.read
project_request.manage

matching.run
matching.inspect

opportunity.read
opportunity.respond
opportunity.manage

quote.read
quote.create
quote.send
quote.accept

conversation.read
conversation.send

booking.read
booking.manage

job.read
job.assign
job.execute
job.complete

provider.read
provider.manage
provider.credentials.manage
provider.credentials.verify
provider.suspend

review.create
review.respond
review.moderate

dispute.create
dispute.manage

integration.read
integration.retry
integration.replay

finance.refund
finance.payout.approve

admin.users.manage
admin.features.manage
admin.audit.read

```

---

# 15. Required Negative Authorization Tests

Mandatory:

```text
Customer A → Customer B ProjectRequest = DENIED

Customer A → Customer B Quote = DENIED

Provider A → Provider B Opportunity = DENIED

Provider A → Provider B Quote = DENIED

Provider A → Provider B Conversation = DENIED

Provider A → Provider B Job = DENIED

Worker → unassigned Job = DENIED

Dispatcher → payout approval = DENIED

Support → credential verification = DENIED

Tenant A → Tenant B = DENIED

```

---

# 16. P0-04 — Capabilities

There must be one authoritative capability service.

Do not create multiple independent capability authorities.

Effective capability:

```text
code available
AND
release/environment enabled
AND
dependencies enabled
AND
provider/runtime ready
AND
environment policy permits

```

Every sensitive mutation checks capabilities server-side.

Required execution formula:

```text
route
AND capability
AND permission
AND record authorization
AND readiness
AND state transition

```

Existing V1 operations representing disabled Marketplace behavior must also be protected.

---

# 17. P0-05 — Idempotency

Add:

```text
idempotency_records

```

Fields:

```text
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

```text
(actor_key, operation, idempotency_key)

```

States:

```text
IN_PROGRESS

COMPLETED

FAILED_RETRYABLE

```

Semantics:

```text
same key + same payload
→ same result

same key + different payload
→ 409

same key currently running
→ conflict/retry

```

---

# 18. Commands Requiring Idempotency

```text
ProjectRequest submit

Provider application submit

Opportunity response

Quote send

Quote revise

Quote accept

Quote decline

Booking confirmation

Booking cancellation

Job assignment

Job state transition

Job completion

Review submission

Dispute creation

Integration retry

Payment later

Refund later

Payout later

```

---

# 19. P0-06 — Concurrency

Standardize aggregate versions.

Required on:

```text
ProjectRequest

Provider

Opportunity

Quote

Booking

Job

```

Expose version using:

```text
ETag

```

Mutation supplies:

```text
If-Match

```

Stale version:

```text
412 PRECONDITION_FAILED

```

Business race:

```text
409 CONCURRENT_MODIFICATION

```

Use row locks where true serialization is required.

---

# 20. Atomic Command Transaction

Every important mutation should commit:

```text
business mutation

+

status/history

+

audit

+

idempotency completion

+

outbox event

```

inside the same PostgreSQL transaction.

---

# 21. P0-07 — Audit

Audit records need:

```text
actor

issuer / subject safe identity

action

resource type

resource ID

tenant

legal entity

request ID

correlation ID

IP

user agent

safe metadata

created at

```

Never log:

```text
password

JWT

authorization header

cookie

API token

private key

full credential number

payment card data

```

---

# 22. P0-08 — Outbox Hardening

Keep the existing durable outbox.

Correct remaining ownership problems.

Outbox record should include:

```text
event ID

event type

schema version

aggregate type

aggregate ID

aggregate version

destination

payload

idempotency key

status

attempt count

max attempts

available_at

claim token

claimed_at

lease expiry

last error code

last redacted error

correlation ID

causation ID

created_at

processed_at

delivered_at

```

---

# 23. Outbox States

```text
PENDING_CONFIGURATION

PENDING

PROCESSING

RETRYABLE

DELIVERED

FAILED_TERMINAL

```

Use actual existing enum names where already established.

Do not create incompatible duplicate statuses merely for documentation consistency.

---

# 24. Outbox Claim Ownership

Claim with:

```text
FOR UPDATE SKIP LOCKED

```

Finalize with:

```sql
UPDATE integration_events
SET ...
WHERE id = :event_id
  AND claim_token = :claim_token
  AND status = 'PROCESSING'

```

Zero updated rows means:

```text
worker lost claim

```

and the worker must not finalize the event.

---

# 25. Outbox Lease

Implement:

```text
bounded provider timeout
+
lease duration

```

and either:

```text
lease heartbeat

```

or safely ensure provider operations cannot exceed the lease.

---

# 26. Canonical Event Registry

Create one event registry.

Naming:

```text
domain.action.v1

```

Examples:

```text
project_request.submitted.v1

provider_application.submitted.v1

provider.approved.v1

matching.started.v1

matching.completed.v1

opportunity.sent.v1

opportunity.accepted.v1

lead.connected.v1

quote.sent.v1

quote.accepted.v1

conversation.message_sent.v1

booking.confirmed.v1

job.assigned.v1

job.completed.v1

review.submitted.v1

credential.verified.v1

dispute.created.v1

```

Unknown event:

```text
FAILED_TERMINAL
UNROUTABLE_EVENT

```

Never silently mark unknown events delivered.

---

# 27. Event Contract Registry

For every event define:

```text
event name

schema version

producer

destinations

payload schema

PII classification

retention

retry policy

ordering requirement

```

---

# 28. P0-09 — Durable Inbox

Add:

```text
integration_inbox

```

Fields:

```text
provider

external_event_id

event_type

schema_version

request_hash

signature_verified

signature_key_id

tenant

legal entity

status

payload

received_at

verified_at

processing_started_at

processed_at

attempt_count

max_attempts

next_attempt_at

lease_owner

lease_expires_at

last_error_code

last_error_redacted

correlation_id

```

Unique:

```text
(provider, external_event_id)

```

---

# 29. Webhook Processing

Every webhook:

```text
raw body

→ maximum-size validation

→ authentication

→ signature validation

→ timestamp validation

→ replay validation

→ event ID

→ durable inbox insert

→ 202

→ inbox worker

→ provider-event translator

→ authorized domain command

→ audit/outbox

```

Never perform long business mutations inside the webhook request.

---

# 30. Webhook Routes

Define separately:

```text
/webhooks/v1/codestra

/webhooks/v1/odoo

/webhooks/v1/klyrow

/webhooks/v1/telnexa

/webhooks/v1/n8n

/webhooks/v1/stripe

```

Only expose a route when its provider contract is configured and reviewed.

---

# 31. Binding Webhook Contract

Every webhook must define:

```text
provider

route

authentication

signature algorithm

signature headers

key rotation

timestamp tolerance

replay ID

maximum request size

uniqueness key

acknowledgement status

acknowledgement deadline

worker

ordering

retry schedule

terminal failure

event → command mapping

retention

redaction

manual replay permission

```

---

# 32. Ops Replay

Add:

```http
POST /api/v2/ops/integration-inbox/{id}/replay

```

Requires:

```text
integration.replay

```

Replay is audited.

Do not delete or mutate history to simulate replay.

---

# 33. P0-10 — Storage

Add:

```text
storage_objects

upload_sessions

```

Purposes:

```text
PROJECT_ATTACHMENT

PROVIDER_CREDENTIAL

PROVIDER_GALLERY

MESSAGE_ATTACHMENT

JOB_EVIDENCE

DISPUTE_EVIDENCE

```

---

# 34. Upload State

```text
PENDING_UPLOAD

UPLOADED

SCANNING

CLEAN

QUARANTINED

REJECTED

DELETED

```

Only:

```text
CLEAN

```

files may be used by domain objects.

---

# 35. Storage API

```http
POST /api/v2/uploads

POST /api/v2/uploads/{id}/complete

GET /api/v2/uploads/{id}

DELETE /api/v2/uploads/{id}

```

Downloads:

```text
authorized
short-lived
signed/controlled
private bucket

```

No permanent public credential URL.

---

# 36. File Policy Matrix

Create a binding policy table:

| Purpose | MIME | Max Size | Malware Scan | Retention | Download Permission |
| --- | --- | --- | --- | --- | --- |
| Project photo | Approved images | Configured | Yes | Configured | Customer/provider |
| Credential | PDF/approved images | Configured | Yes | Compliance policy | Restricted |
| Gallery | Approved images | Configured | Yes | Profile lifetime | Public projection only |
| Message | Approved MIME types | Configured | Yes | Conversation policy | Participants |
| Job evidence | Approved images/PDF | Configured | Yes | Job policy | Authorized parties |
| Dispute evidence | Approved MIME types | Configured | Yes | Legal/dispute policy | Restricted |

Do not hard-code policy values across domain services.

---

# 37. P0-11 — Notifications

Domains emit events.

They do not call Klyrow/Telnexa directly.

Flow:

```text
Domain Event
    ↓
NotificationPolicy
    ↓
NotificationIntent
    ↓
Consent / Preferences
    ↓
Delivery

```

Channels:

```text
IN_APP

EMAIL

SMS

```

Later:

```text
PUSH

```

---

# 38. Notification Tables

```text
notification_intents

notifications

notification_deliveries

```

Delivery states:

```text
PENDING

SENT

DELIVERED

FAILED_RETRYABLE

FAILED_TERMINAL

SUPPRESSED

```

---

# 39. P0-12 — Operational Exceptions

Add:

```text
operational_exceptions

```

Types:

```text
NO_ELIGIBLE_PROVIDER

NO_PROVIDER_RESPONSE

STALE_OPPORTUNITY

QUOTE_OVERDUE

QUOTE_EXPIRED

CREDENTIAL_EXPIRING

CREDENTIAL_EXPIRED

SCHEDULING_CONFLICT

UNASSIGNED_JOB

LATE_JOB

INTEGRATION_RETRY_EXHAUSTED

WEBHOOK_PROCESSING_FAILED

PAYMENT_FAILED

PAYOUT_FAILED

```

States:

```text
OPEN

ACKNOWLEDGED

IN_PROGRESS

RESOLVED

IGNORED

```

Ops must be able to:

```text
acknowledge

assign

note

retry

resolve

```

without direct SQL access.

---

# 40. Adapter Architecture

Define provider-neutral interfaces first.

```text
IdentityProvider

MiddlewareProvider

CrmProvider

EmailProvider

SmsProvider

WorkflowProvider

ObjectStorage

MalwareScanner

Geocoder

BusinessVerificationProvider

CreditDataProvider

PaymentProvider

PayoutProvider

AnalyticsSink

```

---

# 41. Adapter Result

Normalize all vendors into:

```text
provider

success

external_id

retryable

error_code

retry_after_seconds

```

Error classes:

```text
VALIDATION

AUTHENTICATION

AUTHORIZATION

RATE_LIMIT

TIMEOUT

NETWORK

UPSTREAM_5XX

DUPLICATE

CONFIGURATION

TERMINAL

```

Domain code never interprets vendor-specific HTTP codes.

---

# 42. Middleware / Codestra Boundary

Architecture:

```text
BREERO
   ↓
Outbox
   ↓
Worker
   ↓
Middleware Adapter
   ↓
Codestra / Kong
   ├── Odoo
   ├── Klyrow
   ├── Telnexa
   └── n8n

```

The browser never calls these directly.

Machine trust across this boundary requires:

```text
mTLS
+
authenticated/signed request
+
tenant
+
audience
+
scope
+
correlation ID
+
idempotency/replay protection
```

---

# 43. Odoo

Odoo is:

```text
CRM projection

agent workspace

campaign management

follow-up

support workflow

operational reporting

```

It is not authoritative for:

```text
ProjectRequest status

matching

Opportunity status

Quote state

Booking state

Job state

Review state

payment state

```

Odoo → BREERO changes must use authorized commands through middleware/API.

---

# 44. Business Verification / Risk Providers

Provider-neutral foundations may include:

```text
Middesk

```

for business verification and:

```text
Experian

```

for approved credit/risk workflows.

Keep disabled until:

```text
credentials

legal purpose

consent where required

mapping

retention rules

compliance approval

```

are complete.

Vendor data must be normalized into BREERO domain records.

---

# 45. P0-13 — Observability

Required health endpoints:

```http
GET /health/live

GET /health/ready

GET /health/version

```

Version reports:

```text
application version

Git SHA

image digest

migration head

```

No secret configuration.

---

# 46. Readiness

Check:

```text
PostgreSQL

expected migration head

PostGIS availability

required internal dependencies

```

Do not fail readiness because an optional disabled provider is offline.

---

# 47. Metrics

Required:

```text
HTTP request count

latency

4xx

5xx

DB latency

pool utilization

Redis

worker heartbeat

queue depth

outbox backlog

oldest outbox age

inbox backlog

oldest inbox age

terminal integration count

webhook invalid signatures

webhook duplicates

storage scan backlog

quarantine count

```

Marketplace metrics later:

```text
match duration

zero-match rate

provider response time

quote conversion

booking conversion

job completion

```

---

# 48. Tracing

Use OpenTelemetry or equivalent.

Trace:

```text
HTTP

database

workers

outbox

inbox

middleware

vendor adapters

```

Propagate:

```text
trace ID

request ID

correlation ID

```

---

# 49. Alerting

Define thresholds for:

```text
API outage

5xx spike

latency

DB unavailable

DB pool exhaustion

Redis outage

worker heartbeat missing

queue backlog

outbox terminal failures

webhook signature failures

zero-match spike

unassigned jobs

backup failure

restore failure

certificate expiry

```

---

# 50. P0-14 — Database Gate

Missing foundational tables:

```text
external_identities

idempotency_records

integration_inbox

storage_objects

upload_sessions

notification_intents

notifications

notification_deliveries

operational_exceptions

```

Also standardize:

```text
aggregate version fields

history tables

money minor-unit conventions

```

Do not rewrite historical records unless migration semantics are unambiguous.

---

# 51. Migration Validation

For every migration:

```text
empty DB → head

actual current production head → head

PostgreSQL constraints

PostGIS extension

indexes

foreign keys

schema drift

```

The migration head in release documentation must always come from the actual candidate.

Never hard-code stale migration numbers into production authority documents.

---

# 52. API Binding Annex

Create one binding registry row for every V2 endpoint.

Required fields:

```text
method

path

operation ID

request DTO

response DTO

principal

permission

record authorization

capability

idempotency

If-Match/version

state transition

audit action

outbox event

rate limit

PII classification

400 behavior

401 behavior

403 behavior

404 behavior

409 behavior

412 behavior

422 behavior

429 behavior

503 behavior

```

No endpoint is considered fully specified without this row.

---

# 53. Marketplace V2 Domains

After P0:

```text
Catalog

ProjectRequest

Provider Core

Provider Onboarding

Credentials

Availability

Matching

Opportunities

LeadConnection

Quotes

Conversations

Booking Bridge

Jobs

Reviews

Notifications

Disputes

Ops

Admin

```

---

# 54. Marketplace Lifecycle

Canonical lifecycle:

```text
Customer Intent
      ↓
ProjectRequest
      ↓
Qualification
      ↓
Fulfillment Decision
      ↓
Matching
      ↓
Opportunity
      ↓
LeadConnection
      ↓
Conversation + Quote
      ↓
Scheduling
      ↓
Booking
      ↓
Job
      ↓
Completion
      ↓
Verified Review

```

Booking does not own:

```text
qualification

provider discovery

lead generation

quote negotiation

messaging

```

---

# 55. Legacy Migration Mapping

Create a binding migration/compatibility annex.

At minimum define:

```text
PublicSubmission
→ ProjectRequest

Vendor
→ Provider

DispatchOffer
→ Opportunity

```

For ambiguous legacy objects such as WorkRequest, define exact mapping based on existing semantics rather than assuming.

Document:

```text
source object

target object

migration rule

historical compatibility

whether migrated

whether projected

whether left legacy-only

```

---

# 56. Frontend Foundation

Keep:

```text
Next.js

React

TypeScript

```

Do not rewrite to Vue.

Applications:

```text
apps/web

apps/partner

apps/ops

apps/admin

```

Shared:

```text
packages/ui

packages/types

packages/api-client

```

---

# 57. Frontend API Client

Move V2 toward:

```text
FastAPI DTOs
   ↓
OpenAPI
   ↓
generated TypeScript contracts/client
   ↓
application wrapper
   ↓
frontend

```

The handwritten V1 client can remain for V1 compatibility.

Do not mix V1/V2 assumptions invisibly.

---

# 58. Frontend Error Support

Frontend must understand:

```text
code

message

correlation_id

fields

```

Handle:

```text
401

403

404

409

412

422

429

500

503

```

For `429`, honor:

```text
Retry-After

```

---

# 59. Browser Authentication

Make one explicit decision.

Preferred:

```text
Browser
   ↓
Next.js BFF/session
   ↓
secure HttpOnly SameSite cookie
   ↓
OIDC tokens protected server-side
   ↓
FastAPI

```

Do not leave access/refresh-token storage architecture implicit.

If browser bearer tokens remain, approve and document that architecture explicitly.

---

# 60. Frontend Mutation Safety

Important actions must support:

```text
stable Idempotency-Key

If-Match

double-click prevention

loading lock

retry-safe UI

409 reconciliation

412 refresh/reload

429 retry timing

```

---

# 61. Frontend Test Matrix

For every critical form/action prove:

```text
success

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

timeout

retry

double submit

refresh

back navigation

mobile

keyboard

screen reader

```

---

# 62. Realtime Decision

Initial release:

```text
POLLING

```

recommended.

Use:

```text
cursor

updated_since

ETag

```

Potential frequencies:

```text
conversation open:
3–5 sec

job detail:
10–15 sec

opportunities:
15–30 sec

notifications:
30 sec

```

SSE/WebSocket can be introduced later under a separate architecture decision.

---

# 63. If Realtime Is Added

Define before coding:

```text
connection authentication

subscription authorization

sequence numbers

resume cursor

replay

heartbeat

backpressure

token expiration

revocation

connection limits

```

---

# 64. Security Gate

Production security includes:

```text
OIDC

issuer/subject identity

record-level authorization

RBAC permissions

capabilities

idempotency

concurrency

CORS

CSRF where applicable

CSP

rate limiting

request limits

secret management

PII masking

file scanning

webhook verification

replay protection

dependency scanning

container scanning

audit

```

---

# 65. Secrets

Never commit:

```text
database passwords

JWT secrets

OIDC client secrets

API tokens

HMAC secrets

mTLS private keys

payment secrets

SMTP credentials

```

Production secrets come from:

```text
secret manager

```

or:

```text
mounted secret files

```

Startup must fail if required production secrets are unavailable.

---

# 66. Gateway / Public Exposure

Explicitly configure:

```text
/api/v1

/api/v2

approved /webhooks/v1/*

```

Explicitly deny:

```text
/internal/**

```

Internal metrics, worker endpoints, admin-only diagnostics and infrastructure APIs must not be publicly reachable.

---

# 67. Backup

Implement:

```text
scheduled PostgreSQL backup

encryption

off-host copy

checksum

retention

backup monitoring

```

For required RPO:

```text
WAL / PITR

```

---

# 68. Restore

Automated rehearsal:

```text
choose backup

→ isolated DB

→ checksum verify

→ restore

→ migration verify

→ API boot

→ smoke test

→ record evidence

→ destroy isolated environment

```

A backup is not proven until restore succeeds.

---

# 69. RPO / RTO Annex

Define exact production targets:

```text
RPO=

RTO=

maximum tolerated outbox age=

maximum tolerated inbox age=

maximum worker heartbeat age=

maximum API latency target=

maximum allowed 5xx rate=

```

These become monitoring/alert thresholds.

---

# 70. Data Governance Annex

Define for every sensitive dataset:

```text
owner

classification

retention

deletion

access

export policy

legal hold

backup retention

log redaction

```

Cover:

```text
ProjectRequests

messages

customer photos

credentials

job evidence

dispute evidence

CRM projections

integration payloads

audit

payments

```

---

# 71. CI

Backend PR:

```text
Ruff

MyPy

compile

unit

domain

PostgreSQL

PostGIS

migration empty→head

migration current→head

schema drift

authentication negative tests

authorization negative tests

idempotency

concurrency

outbox

inbox

webhook security

OpenAPI

dependency audit

container build

container scan

```

Frontend:

```text
lint

typecheck

unit

component

contract

build

browser E2E

viewport

accessibility

```

---

# 72. Immutable Build

Every production image must be traceable to:

```text
source SHA

image digest

migration head

config checksum

SBOM

signature

provenance

```

Never deploy:

```text
latest

```

as release identity.

---

# 73. Staging

Staging must match production architecture:

```text
same image

same PostgreSQL major version

same PostGIS model

same Redis model

same worker topology

same gateway model

same migrations

```

with different:

```text
database

credentials

storage

provider tenants

feature flags

recipient allowlists

```

---

# 74. Staging Vendor Safety

For each provider define:

```text
sandbox account

safe mode

recipient allowlist

transaction cap

environment guard

```

No staging environment should accidentally send unrestricted production email/SMS/payment activity.

---

# 75. Staging Vertical Slice

Before production prove:

```text
OIDC login

→ ProjectRequest

→ questionnaire

→ upload

→ submit

→ qualification

→ matching

→ Opportunity

→ provider acceptance

→ LeadConnection

→ conversation

→ Quote

→ acceptance

→ Booking

→ assignment

→ Job

→ completion

→ Review

```

using the exact production candidate.

---

# 76. Staging Failure Slice

Also prove:

```text
wrong issuer denied

wrong audience denied

cross-customer denied

cross-provider denied

unassigned worker denied

disabled capability denied

expired credential excluded

suspended provider excluded

duplicate submit safe

duplicate Opportunity acceptance safe

duplicate Quote acceptance safe

duplicate webhook safe

middleware outage safe

stale worker safe

quarantined upload unusable

```

---

# 77. Deployment

Production:

```text
CI green

→ immutable image

→ staging

→ staging E2E

→ approval

→ database backup

→ migration preflight

→ canary

→ smoke

→ metrics/log validation

→ controlled rollout

→ monitored soak

```

No production deployment from a developer laptop.

---

# 78. Canary

Define:

```text
traffic percentage

user cohort

tenant cohort

duration

automatic abort metrics

manual abort owner

```

Dangerous Marketplace capabilities may remain off even while code is deployed.

---

# 79. Rollback

Every release has:

```text
previous image digest

previous config

migration compatibility status

rollback command

backup reference

rollback verification steps

```

Prefer backward-compatible database migrations so application rollback does not require database restoration.

---

# 80. Production Activation

Separate:

```text
DEPLOYMENT

```

from:

```text
FEATURE ACTIVATION

```

Example:

```text
matching code deployed=true

matching capability enabled=false

```

Then:

```text
staging certified
+
security approved
+
operations ready
+
provider data ready
+
monitoring ready

```

before activation.

---

# 81. Feature Activation Matrix

Maintain:

| Capability | Code | Code Ready | Staging | Security | Ops | External Dependency | Production Enabled |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Matching | `marketplace_matching` | Yes/No | Yes/No | Yes/No | Yes/No | Yes/No | Yes/No |
| Provider self-service | `provider_self_service` | Yes/No | Yes/No | Yes/No | Yes/No | Yes/No | Yes/No |
| Quotes | `quotes` | Yes/No | Yes/No | Yes/No | Yes/No | Yes/No | Yes/No |
| Messaging | `messaging` | Yes/No | Yes/No | Yes/No | Yes/No | Yes/No | Yes/No |
| Reviews | `reviews` | Yes/No | Yes/No | Yes/No | Yes/No | Yes/No | Yes/No |
| Automatic assignment | `automatic_assignment` | Yes/No | Yes/No | Yes/No | Yes/No | Yes/No | Yes/No |
| Payments | `online_payments` | Yes/No | Yes/No | Yes/No | Yes/No | Yes/No | Yes/No |
| Payouts | `payouts` | Yes/No | Yes/No | Yes/No | Yes/No | Yes/No | Yes/No |

---

# 82. Implementation Sequence

The binding order is:

```text
1 API foundation corrections

2 Production OIDC authentication

3 External identities

4 Principal / permissions

5 Record-level authorization

6 Capability enforcement

7 Generic idempotency

8 Standard concurrency

9 Audit context

10 Outbox hardening

11 Durable inbox/webhooks

12 Private storage/uploads

13 Malware scanning

14 Notifications

15 Operational exceptions

16 Observability

17 Backup/restore

18 Deployment/security configuration

19 P0 PostgreSQL/PostGIS gate

──────── P0_FINAL ────────

20 Catalog

21 ProjectRequest

22 Provider Core

23 Provider onboarding

24 Credentials

25 Availability

26 Matching

27 Opportunities

28 LeadConnection

29 Quotes

30 Conversations

31 Booking bridge

32 Jobs

33 Reviews

34 Disputes

35 Ops

36 Admin

37 Generated frontend V2 client

38 Customer UI

39 Provider UI

40 Worker UI

41 Ops UI

42 Admin UI

43 Complete staging E2E

44 Canary

45 Controlled activation

```

## Approved branch map

P0 branches:

```text
be/marketplace-v2-p0-api-foundation
be/marketplace-v2-p0-authentication
be/marketplace-v2-p0-authorization
be/marketplace-v2-p0-capabilities-idempotency
be/marketplace-v2-p0-integration-reliability
be/marketplace-v2-p0-storage-uploads
be/marketplace-v2-p0-observability-operations
```

Core marketplace branches:

```text
be/marketplace-v2-catalog
be/marketplace-v2-project-requests
be/marketplace-v2-provider-core
be/marketplace-v2-provider-trust
be/marketplace-v2-provider-availability
be/marketplace-v2-matching
be/marketplace-v2-opportunities
be/marketplace-v2-quotes
be/marketplace-v2-messaging
be/marketplace-v2-booking-job
be/marketplace-v2-reviews
be/marketplace-v2-notifications
be/marketplace-v2-disputes
be/marketplace-v2-ops
be/marketplace-v2-admin
```

Frontend branches begin only after stable backend contracts:

```text
fe/marketplace-v2-p0-api-auth
fe/marketplace-v2-customer
fe/marketplace-v2-partner
fe/marketplace-v2-ops
fe/marketplace-v2-admin
```

The Odoo campaign implementation remains in its separate `crm/odoo-*` authority and never becomes authoritative for marketplace state.

---

# 83. Independently Reviewable PR Rule

Every approved implementation workstream must be delivered as a separate reviewable PR. Tightly coupled numbered steps may share one PR only when the approved branch map groups them together; unrelated work must not be bundled.

Each PR contains:

```text
scope

non-goals

base SHA

architecture impact

database changes

domain changes

API changes

permissions

capabilities

idempotency

concurrency

audit

events

tests

security

observability

rollback

known risks

```

---

# 84. PR Evidence Block

Every PR ends with:

```text
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
INBOX_TESTS=
WEBHOOK_TESTS=

OPENAPI_STATUS=

TYPECHECK_STATUS=
FRONTEND_TESTS=
PLAYWRIGHT_STATUS=
ACCESSIBILITY_STATUS=

SECURITY_SCAN=

OBSERVABILITY_STATUS=

CAPABILITIES_ENABLED=

EXTERNAL_SENDS_ENABLED=

PRODUCTION_DB_TOUCHED=NO

SECRETS_EXPOSED=NO

KNOWN_RISKS=

ROLLBACK=

BLOCKERS=

NEXT_SAFE_ACTION=

```

---

# 85. Endpoint Definition of Done

An endpoint is not complete merely because it responds.

It is complete when:

```text
request DTO defined

response DTO defined

operation ID stable

auth defined

permission defined

record policy defined

capability defined

idempotency defined

version behavior defined

state transition defined

audit defined

event defined

rate limit defined

PII defined

errors defined

OpenAPI generated

tests green

```

---

# 86. Webhook Definition of Done

A webhook is complete when:

```text
provider defined

route defined

auth defined

signature defined

timestamp defined

replay ID defined

size limit defined

raw hash stored

durable inbox used

unique event enforced

ACK behavior defined

worker implemented

retry implemented

terminal state implemented

Ops replay implemented

retention defined

redaction defined

tests green

```

---

# 87. Domain Definition of Done

A domain is complete when:

```text
aggregate defined

commands defined

state machine defined

policies defined

authorization defined

repository defined

queries defined

history defined

audit defined

events defined

idempotency defined

concurrency defined

migration complete

unit tests green

PostgreSQL tests green

cross-actor negative tests green

```

---

# 88. Production Definition of Done

Production Marketplace V2 requires:

```text
P0_FINAL=PASS

all required domains PASS

all required endpoint contracts PASS

all enabled webhook contracts PASS

all enabled adapter contracts PASS

frontend E2E PASS

authorization negative suite PASS

idempotency PASS

concurrency PASS

migration rehearsal PASS

backup PASS

restore PASS

observability PASS

staging PASS

canary PASS

rollback ready

operations ready

security approval complete

```

Only then:

```text
MARKETPLACE_V2=GO

```

---

# 89. Required Final Release Manifest

Before activation produce:

```text
FINAL_STATUS=

SOURCE_SHA=

IMAGE_DIGEST=

MIGRATION_HEAD=

CONFIG_CHECKSUM=

SBOM_DIGEST=

SIGNATURE_STATUS=

OIDC_STATUS=

AUTHORIZATION_STATUS=

CAPABILITY_STATUS=

AUDIT_STATUS=

IDEMPOTENCY_STATUS=

CONCURRENCY_STATUS=

OUTBOX_STATUS=

INBOX_STATUS=

WEBHOOK_STATUS=

STORAGE_STATUS=

NOTIFICATION_STATUS=

OPERATIONAL_EXCEPTION_STATUS=

ADAPTER_STATUS=

FRONTEND_STATUS=

OPS_STATUS=

OBSERVABILITY_STATUS=

DATABASE_STATUS=

SECURITY_STATUS=

GATEWAY_STATUS=

RELEASE_PIPELINE_STATUS=

BACKUP_STATUS=

RESTORE_STATUS=

STAGING_STATUS=

CANARY_STATUS=

ROLLBACK_STATUS=

PRODUCTION_FEATURES_ENABLED=

BLOCKERS=

NEXT_SAFE_ACTION=

```

---

# 90. Current Decision

Based on the current implementation state:

```text
REQUEST_ONLY_V1=PARTIAL

MARKETPLACE_V2=NO_GO

PRODUCTION_READY=NO

P0_FINAL=FAIL

```

The correct next work remains:

```text
API foundation corrections

→ authentication

→ identity

→ authorization

→ capabilities

→ idempotency/concurrency

→ audit

→ outbox

→ inbox/webhooks

→ storage

→ notifications/exceptions

→ observability/security/database

→ P0_FINAL

→ Catalog

```

No Marketplace feature should bypass this sequence.

---

# 91. Codex Master Instruction

Use the following as the implementation directive:

> Reconcile the current codebase against this Production Completion Blueprint. Preserve existing working architecture and compatibility. Do not introduce duplicate identity systems, capability authorities, database models, event mechanisms or integration layers. Implement each production gap as a separate independently reviewable PR in the prescribed order. For every mutation, enforce authentication, permission, record authorization, capability, valid state, idempotency and concurrency as applicable. Commit business mutation, history, audit, idempotency completion and outbox event atomically. Route outbound integrations through the durable outbox and provider-neutral adapters. Route inbound external activity through authenticated, replay-protected durable inbox records and asynchronous workers. Keep CRM, middleware and external providers subordinate to the core application's authoritative domain state. Add migrations, PostgreSQL/PostGIS tests, negative authorization tests, concurrency tests, OpenAPI contracts, operational recovery, observability, backup/restore evidence and rollback instructions. Keep dangerous capabilities disabled until staging, security, operations and dependency gates explicitly approve activation. Do not report production readiness unless every mandatory gate passes on the exact final candidate SHA.
