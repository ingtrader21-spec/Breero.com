# Marketplace V2

# Corrected Production Blueprint + Implementation Package

## Package structure

```text
docs/marketplace-v2/
├── 00_PRODUCTION_BLUEPRINT.md
├── 01_P0_IMPLEMENTATION_PACKAGE.md
├── 02_API_CONTRACT_REGISTRY.md
├── 03_WEBHOOK_INTEGRATION_REGISTRY.md
├── 04_SECURITY_AUTHORIZATION_MATRIX.md
├── 05_EVENT_REGISTRY.md
├── 06_DATA_FILE_RETENTION_POLICY.md
├── 07_PRODUCTION_READINESS_GATES.md
├── 08_RELEASE_RUNBOOK.md
└── 09_PR_IMPLEMENTATION_TEMPLATE.md
```

## Document status

This package is the binding implementation authority for Marketplace V2 production work.

It supersedes earlier drafts where they conflict with this document.

This package does **not** activate Marketplace V2.

Current high-level status remains:

```text
REQUEST_ONLY_V1=PARTIAL
MARKETPLACE_V2=NO_GO
PRODUCTION_READY=NO
P0_FINAL=FAIL
```

Implementation must proceed through the production gates defined below.

---
# PRODUCTION BLUEPRINT

## 1. Objective

Build a production-grade two-sided marketplace and provider SaaS platform using the established application architecture.

The system consists of:

```
Customer Web
Provider Portal
Worker Experience
Operations Portal
Administration Portal
        │
        ▼
Backend API
        │
        ▼
Commands
        │
        ▼
Domain Services
        │
 ┌──────┼─────────────┐
 ▼      ▼             ▼
Policy  Authorization State Machine
        │
        ▼
Repository / Queries
        │
        ▼
PostgreSQL / PostGIS
        │
 ┌──────┼───────────────┐
 ▼      ▼               ▼
Audit  Idempotency     Outbox
                          │
                          ▼
                       Workers
                          │
                          ▼
                       Adapters
                          │
                          ▼
                 Middleware / Providers
```

Inbound integrations:

```
External Provider
      │
      ▼
Webhook
      │
      ▼
Authentication / Signature
      │
      ▼
Durable Inbox
      │
      ▼
Inbox Worker
      │
      ▼
Translator
      │
      ▼
Authorized Domain Command
```

---

# 2. Established Technology

Preserve the established stack.

Frontend:

```
Next.js
React
TypeScript
```

Backend:

```
Python
FastAPI
Async SQLAlchemy
Alembic
```

Persistence:

```
PostgreSQL
PostGIS
Redis
```

Workers:

```
existing Celery/background-worker infrastructure
```

Repository architecture remains a monorepo.

Do not:

```
rewrite frontend to Vue

split into unrelated repositories

replace PostgreSQL as system of record

introduce microservices merely to separate workers
```

---

# 3. Applications

Frontend applications:

```
apps/web
    customer marketplace

apps/partner
    provider/business portal
    worker experience

apps/ops
    operational recovery/control

apps/admin
    administration/security/configuration
```

Shared packages:

```
packages/ui
packages/types
packages/api-client
```

---

# 4. Source-of-Truth Rules

## Core backend owns

```
Customer

Property

Catalog

ProjectRequest

Provider

Provider Membership

Worker

Credentials

Availability

Matching

Opportunity

LeadConnection

Quote

Conversation

Booking

Job

Review

Dispute

Notification state

Marketplace operational state
```

## PostgreSQL/PostGIS owns

Authoritative persisted business and geographic state.

## Redis owns

Derived/disposable state only:

```
cache

rate limits

temporary locks

worker queues

circuit-breaker state
```

## CRM owns

CRM workflow and projections only.

It must not own Marketplace aggregate state.

## Middleware/control plane owns

Integration transport/orchestration.

It must not own marketplace business truth.

---

# 5. Canonical Marketplace Lifecycle

```
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

```
qualification

provider discovery

lead generation

quote negotiation

conversation
```

---

# 6. Fulfillment Modes

```
INSTANT_BOOK

QUOTE_REQUIRED

MANUAL_DISPATCH

UNSERVICEABLE
```

Initial implementation must be deterministic/configurable.

Do not introduce machine-learning matching in V1 of Marketplace V2.

---

# 7. Production Feature Principle

```
CODE_AVAILABLE
AND
ENVIRONMENT_ENABLED
AND
RELEASE_FLAG_ENABLED
AND
DEPENDENCIES_READY
AND
PROVIDER_READY
AND
ENVIRONMENT_POLICY_APPROVED
=
CAPABILITY_EFFECTIVE
```

Dangerous capabilities default disabled.

Examples:

```
matching

provider_self_service

opportunities

quotes

messaging

reviews

instant_booking

automatic_assignment

payments

payouts

paid_leads

marketing
```

---

# 8. Canonical Capability Authority

Existing capability implementation remains authoritative.

Canonical public endpoint:

```
GET /api/v1/public/capabilities
```

Do not create an independent:

```
/api/v2/capabilities
```

source of truth.

If a V2 projection/alias is ever introduced, it must call the exact same capability service and require separate contract approval.

Every backend command must enforce capability independently of the frontend.

---

# 9. Shared Production Infrastructure

Implement as reusable first-class infrastructure:

```
Principal

CommandContext

Permissions

RecordPolicy

CapabilityRegistry / existing CapabilityService integration

IdempotencyService

OptimisticConcurrency

AuditService

DomainEvent

TransactionalOutbox

IntegrationInbox

IntegrationAdapter

ProviderResult

CorrelationContext

ProblemDetails/ErrorContract
```

---

# 10. Command Transaction Rule

A high-value mutation should normally commit:

```
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

inside one PostgreSQL transaction.

No external HTTP provider call is part of that transaction.

---

# 11. API Layer

API routes remain thin.

Allowed responsibilities:

```
parse HTTP request

authenticate

construct Principal

construct CommandContext

validate transport DTO

invoke domain command/query

serialize response
```

Business rules do not belong in routers.

---

# 12. Domain Layer

Recommended domain structure:

```
domains/<domain>/

models.py
schemas.py
commands.py
service.py
policies.py
state_machine.py
repository.py
queries.py
events.py
errors.py
```

Create only files with real responsibilities.

---

# 13. Authentication

Production human identity:

```
OIDC
Authorization Code + PKCE
```

Machine identity:

```
OAuth client credentials
```

Production must not rely on local password/JWT authentication.

Production startup should fail when authoritative OIDC configuration is absent.

---

# 14. Canonical Identity Provider

Canonical issuer:

```
https://auth.codestra.co/realms/codestra
```

Do not use:

```
https://auth.codestra.agency/...
```

as the production issuer.

---

# 15. Token Validation

Validate:

```
signature

iss

aud

azp when required

exp

nbf

iat

sub

kid

algorithm
```

JWKS handling:

```
process-wide cache

unknown kid
→ refresh JWKS/discovery once
→ retry

still invalid
→ reject
```

Never instantiate a fresh JWKS client for each request.

---

# 16. External Identity Binding

Create:

```
external_identities
```

Fields:

```
id UUID PK

user_id UUID FK

issuer VARCHAR NOT NULL

subject VARCHAR NOT NULL

email_at_link_time VARCHAR NULL

created_at TIMESTAMPTZ

last_seen_at TIMESTAMPTZ
```

Unique:

```
(issuer, subject)
```

Identity flow:

```
OIDC token
→ validate
→ issuer + subject
→ external identity
→ local user
→ memberships
→ permissions
→ Principal
```

Email is profile data, not identity authority.

---

# 17. Principal

Conceptual Principal:

```
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

---

# 18. Authorization Formula

Every protected operation:

```
Authenticated

AND

Permission

AND

Tenant access

AND

Legal-entity access

AND

Record ownership/provider membership/worker assignment

AND

Resource state permits operation
```

---

# 19. Roles

Recommended roles:

```
CUSTOMER

PROVIDER_OWNER

PROVIDER_MANAGER

WORKER

DISPATCHER

CUSTOMER_SUPPORT

TRUST_SAFETY

FINANCE

ADMIN

SUPER_ADMIN
```

Dispatcher must not inherit finance authority.

---

# 20. Core Permissions

```
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

# 21. Authorized Repository Pattern

Prefer:

```
quote_for_provider(id, provider_id)

project_request_for_customer(id, customer_id)

job_for_worker(id, worker_id)
```

over:

```
get arbitrary record
then authorize later
```

Cross-tenant/private resource access may return `404` where appropriate.

---

# 22. CommandContext

Create from the real HTTP request:

```
actor_id

issuer

subject

roles/permissions context

request_id

correlation_id

tenant_id

legal_entity_id

provider_id where relevant

worker_id where relevant

idempotency_key

ip_address

user_agent
```

Propagate into:

```
audit

domain events

outbox

integration requests

structured logs

traces
```

---

# 23. API Error Contract

V2 error:

```
{
  "code": "RESOURCE_CONFLICT",
  "message": "The requested change conflicts with the current resource state.",
  "correlation_id": "...",
  "fields": null
}
```

Statuses:

```
400 malformed

401 authentication

403 authorization

404 unavailable/not found

409 state/idempotency/domain conflict

412 stale version/precondition

422 validation

429 rate limit

500 internal

503 required dependency unavailable
```

Preserve:

```
WWW-Authenticate

Retry-After

ETag
```

Unexpected exceptions must produce the V2 envelope with correlation ID and must not expose stack traces.

---

# 24. Idempotency

Create:

```
idempotency_records
```

Fields:

```
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

Rules:

```
same key + same payload
→ replay result

same key + different payload
→ 409

same key currently executing
→ conflict/retry response
```

---

# 25. Required Idempotent Operations

```
ProjectRequest submit

Provider application submit

Opportunity response

Quote send

Quote revise

Quote accept/decline

Booking confirmation/cancellation

Job assignment

Job state transitions

Job completion

Review submission

Dispute creation

Integration retry

Payments/refunds/payouts later
```

---

# 26. Concurrency

Use aggregate `version`.

Required for:

```
ProjectRequest

Provider

Opportunity

Quote

Booking

Job
```

REST mutation uses:

```
If-Match: "<version>"
```

Stale:

```
412 PRECONDITION_FAILED
```

Domain race:

```
409 CONCURRENT_MODIFICATION
```

Use row locks where true serialization is required.

---

# 27. Audit

Audit fields:

```
actor_id

issuer/subject safe identifiers

action

resource_type
resource_id

tenant_id
legal_entity_id

request_id
correlation_id

ip_address
user_agent

safe metadata

created_at
```

Never store secrets in audit metadata.

---

# 28. Transactional Outbox

Outbound integration flow:

```
Domain command
     ↓
Business state + outbox
     ↓
COMMIT
     ↓
Worker
     ↓
Destination Router
     ↓
Adapter
     ↓
Provider
```

Preserve the established outbox and harden it.

---

# 29. Outbox States

Use actual repository enum naming.

Conceptually:

```
PENDING_CONFIGURATION

PENDING

PROCESSING

RETRYABLE / existing equivalent

DELIVERED

FAILED_TERMINAL
```

Do not create duplicate states solely to match documentation.

---

# 30. Outbox Record

Required concepts:

```
event_id

event_type

schema_version

aggregate_type
aggregate_id
aggregate_version

destination

payload

idempotency_key

status

attempt_count
max_attempts

available_at

claim_token
claimed_at
lease_expires_at

last_error_code
last_error_message_redacted

correlation_id
causation_id

created_at
processed_at
delivered_at
```

---

# 31. Claim Correctness

Claim with:

```
SELECT ... FOR UPDATE SKIP LOCKED
```

Finalize conditionally:

```
UPDATE integration_events
SET ...
WHERE id = :id
AND claim_token = :claim_token
AND status = 'PROCESSING';
```

If zero rows update:

```
claim lost
→ worker does not finalize
```

Long processing uses bounded timeouts and lease heartbeat/extension where necessary.

---

# 32. Unknown Events

Never:

```
unknown event
→ DELIVERED
```

Instead:

```
FAILED_TERMINAL

error_code=UNROUTABLE_EVENT
```

Create operational exception if appropriate.

---

# 33. Canonical Event Naming

New Marketplace V2 events:

```
domain.action.v1
```

Examples:

```
project_request.created.v1

project_request.submitted.v1

project_request.qualified.v1

provider_application.submitted.v1

provider.approved.v1

provider.suspended.v1

matching.started.v1

matching.completed.v1

opportunity.sent.v1

opportunity.accepted.v1

lead.connected.v1

quote.sent.v1

quote.revised.v1

quote.accepted.v1

conversation.message_sent.v1

booking.confirmed.v1

job.assigned.v1

job.en_route.v1

job.arrived.v1

job.started.v1

job.completed.v1

review.submitted.v1

credential.submitted.v1

credential.verified.v1

credential.expiring.v1

credential.expired.v1

credential.revoked.v1

dispute.created.v1

dispute.resolved.v1

communication.preference_changed.v1
```

Legacy event compatibility must use explicit translation.

Do not silently rename historical events.

---

# 34. Durable Integration Inbox

Create:

```
integration_inbox
```

Fields:

```
provider

external_event_id

event_type

schema_version

request_hash

signature_verified
signature_key_id

tenant_id
legal_entity_id

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
last_error_message_redacted

correlation_id
```

Unique:

```
(provider, external_event_id)
```

---

# 35. Webhook Flow

```
raw body

→ body-size check

→ provider authentication

→ signature verification

→ timestamp verification

→ replay validation

→ external event ID

→ payload hash

→ durable inbox insert

→ 202

→ asynchronous worker

→ provider translator

→ authorized domain command

→ domain transaction
```

Do not execute complex business mutations synchronously inside webhook handlers.

---

# 36. Webhook Routes

Reserved contracts:

```
POST /webhooks/v1/codestra

POST /webhooks/v1/odoo

POST /webhooks/v1/klyrow

POST /webhooks/v1/telnexa

POST /webhooks/v1/n8n

POST /webhooks/v1/stripe
```

Do not publicly activate routes until their integration contract and credentials are approved.

---

# 37. Webhook Replay

Ops:

```
POST /api/v2/ops/integration-inbox/{id}/replay
```

Requires:

```
integration.replay
```

Manual replay must:

```
record reason

write audit

preserve old inbox record/history
```

---

# 38. Storage

Create:

```
storage_objects

upload_sessions
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

---

# 39. Upload Lifecycle

```
PENDING_UPLOAD

→ UPLOADED

→ SCANNING

→ CLEAN
```

or:

```
→ QUARANTINED

→ REJECTED
```

Final:

```
DELETED
```

Only `CLEAN` objects may be used by business aggregates.

---

# 40. Storage API

```
POST   /api/v2/uploads

POST   /api/v2/uploads/{id}/complete

GET    /api/v2/uploads/{id}

DELETE /api/v2/uploads/{id}
```

Storage must be private.

Sensitive documents must never receive permanent public URLs.

---

# 41. Storage Adapter

Domain/API uses provider-neutral:

```
ObjectStorage
```

Possible implementation may later be:

```
Azure Blob

S3-compatible storage

MinIO
```

without changing domain logic.

---

# 42. Malware Scanner

Provider-neutral:

```
MalwareScanner
```

Scanner result controls storage state.

Malware provider callback must enter through durable inbox if asynchronous.

---

# 43. Geocoding

Provider-neutral:

```
Geocoder
```

Input:

```
address
```

Output:

```
normalized address

latitude

longitude

timezone
```

Geocoder does not decide service eligibility.

PostGIS does.

---

# 44. Notifications

Domain services do not call email/SMS directly.

Flow:

```
Domain Event
    ↓
NotificationPolicy
    ↓
NotificationIntent
    ↓
Consent / Preferences
    ↓
Delivery channel
```

Channels:

```
IN_APP

EMAIL

SMS
```

---

# 45. Notification Tables

```
notification_intents

notifications

notification_deliveries
```

States:

```
PENDING

SENT

DELIVERED

FAILED_RETRYABLE

FAILED_TERMINAL

SUPPRESSED
```

Existing communication consent/suppression remains authoritative.

---

# 46. Operational Exceptions

Create durable:

```
operational_exceptions
```

Types include:

```
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

```
OPEN

ACKNOWLEDGED

IN_PROGRESS

RESOLVED

IGNORED
```

---

# 47. Adapter Layer

Provider-neutral contracts:

```
KeycloakIdentityProvider

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

# 48. ProviderResult

All integration adapters normalize result into:

```
provider

success

external_id

retryable

error_code

retry_after_seconds
```

Error classes:

```
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

---

# 49. Middleware Boundary

Preferred:

```
Domain
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

No browser directly invokes these systems.

---

# 50. Odoo Boundary

Odoo is a CRM projection and agent workspace.

Odoo may own:

```
campaign

CRM stage

agent notes

activities

disposition

follow-up

agent assignment inside CRM workflow
```

Odoo does not own:

```
ProjectRequest state

matching result

Opportunity state

Quote state

Booking state

Job state

provider eligibility

Review state

payment state
```

Odoo outbound business actions become commands through approved integration APIs.

---

# 51. Klyrow Boundary

Klyrow is the email delivery provider.

Use through:

```
NotificationPolicy
→ EmailProvider
```

Delivery callbacks enter durable inbox.

---

# 52. Telnexa Boundary

Telnexa is SMS delivery.

Use through:

```
NotificationPolicy
→ SmsProvider
```

Delivery callbacks enter durable inbox.

---

# 53. n8n Boundary

n8n may execute approved automation workflows.

Every workflow must be allowlisted.

n8n must never directly update business tables.

---

# 54. Business Verification

Business verification may use a provider such as Middesk through:

```
BusinessVerificationProvider
```

Remain disabled until:

```
credentials

business/legal requirements

mapping

retention

compliance approval
```

are supplied.

---

# 55. Credit / Risk Integration

Risk/credit providers such as Experian are accessed through:

```
CreditDataProvider
```

Remain disabled until:

```
legal purpose

consent where applicable

credentials

product contract

data retention

access-control policy
```

are approved.

---

# 56. Payment Architecture

Payments later:

```
PaymentProvider
```

Possible implementation:

```
Stripe
```

Keep:

```
payments=false
```

until separate activation.

Payout capability is separate.

---

# 57. Background Workers

Logical processes:

```
API

Outbox Worker

Inbox Worker

Notification Worker

Scheduler

File Scan Worker
```

Use established worker infrastructure.

No microservice split required.

---

# 58. Scheduler

Scheduled jobs include:

```
expire temporary holds

expire opportunities

expire quotes

stale ProjectRequests

credential warnings

credential expiration

unassigned jobs

late jobs

review reminders

integration housekeeping

retention

payment reconciliation later
```

---

# 59. Observability

Structured logs:

```
timestamp

level

event

request ID

correlation ID

actor safe ID

tenant safe ID

provider/resource IDs where safe

duration

status
```

Never log:

```
password

JWT

cookies

Authorization

API secrets

private keys

full credential numbers

card data
```

---

# 60. Metrics

Infrastructure:

```
HTTP requests

latency

errors

DB latency

DB pool

Redis

worker heartbeat

queue depth
```

Integration:

```
outbox pending count

outbox oldest age

outbox terminal failures

inbox pending count

inbox oldest age

webhook invalid signatures

webhook duplicates

upload scanning backlog

quarantine count
```

Marketplace later:

```
matching duration

zero-match rate

Opportunity acceptance

provider response time

Quote conversion

Booking conversion

Job completion
```

---

# 61. Tracing

Use OpenTelemetry or equivalent.

Propagate:

```
trace ID

request ID

correlation ID
```

through:

```
API

DB

worker

outbox

inbox

middleware

provider adapter
```

---

# 62. Health

```
GET /health/live

GET /health/ready

GET /health/version
```

`/health/version` reports safe metadata:

```
application version

Git SHA

image digest

migration head
```

Readiness checks only required dependencies.

Disabled optional provider failures do not make API unready.

---

# 63. Frontend Architecture

Keep Next.js/React.

Customer:

```
apps/web
```

Provider/worker:

```
apps/partner
```

Operations:

```
apps/ops
```

Administration:

```
apps/admin
```

---

# 64. Frontend API Contracts

Preferred V2 flow:

```
FastAPI/Pydantic
 ↓
OpenAPI
 ↓
generated TypeScript contracts/client
 ↓
thin application wrapper
 ↓
frontend
```

Do not continue scaling V2 through unrelated handwritten DTO duplication.

---

# 65. Frontend Errors

Support:

```
code

message

correlation_id

fields
```

Handle:

```
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

Honor `Retry-After`.

---

# 66. Browser Authentication

Preferred production architecture:

```
Browser
   ↓
Next.js BFF/session
   ↓
Secure HttpOnly SameSite cookie
   ↓
OIDC tokens protected server-side
   ↓
FastAPI
```

If browser bearer tokens remain, make it an explicit approved security decision.

Do not leave `sessionStorage` token handling as an accidental architecture.

---

# 67. Frontend Mutation Safety

High-value mutations implement:

```
stable Idempotency-Key

If-Match

double-submit protection

loading state

conflict handling

safe retry

412 refresh behavior

429 Retry-After handling
```

---

# 68. Realtime

Initial Marketplace release:

```
POLLING
```

Use:

```
cursor

updated_since

ETag
```

SSE/WebSocket requires separate ADR before implementation.

---

# 69. Database Standards

Use:

```
UUID

TIMESTAMPTZ

BIGINT minor money

CHAR(3) currency

JSONB where justified

PostGIS geometry/geography

integer aggregate version
```

Do not use floating point for money.

New Marketplace money should be BIGINT minor units.

Legacy ambiguous money fields should be migrated safely rather than destructively rewritten.

---

# 70. Migration Strategy

```
EXPAND

→ compatible deployment

→ BACKFILL

→ validate

→ CONTRACT
```

For each migration:

```
empty DB → head

actual candidate/current production head → head

PostgreSQL tests

PostGIS tests

constraints

indexes

schema drift
```

Never rely on stale migration numbers written in documentation.

Release tooling must query the actual Alembic head.

---

# 71. Backup

Implement:

```
automated PostgreSQL backup

encryption

off-host storage

retention

checksum

monitoring
```

Use PITR/WAL where required by approved RPO.

---

# 72. Restore

Rehearsal:

```
backup

→ isolated database

→ verify checksum

→ restore

→ verify migration

→ boot API

→ smoke test

→ record result

→ destroy restore environment
```

A backup is not proven until restore succeeds.

---

# 73. CI

Backend:

```
Ruff

MyPy

compile

unit/domain tests

PostgreSQL tests

PostGIS tests

Alembic empty→head

current-head→head

schema drift

auth negative tests

authorization tests

idempotency

concurrency

outbox/inbox

webhook security

OpenAPI

dependency audit

container build

container scan
```

Frontend:

```
lint

typecheck

unit/component

contract

build

Playwright

viewport

accessibility
```

---

# 74. Immutable Build

Release identifies:

```
source SHA

image digest

migration head

config checksum

SBOM digest

signature

provenance
```

Never use `latest` as authoritative release identity.

---

# 75. Staging

Staging mirrors production architecture.

Same:

```
application image

PostgreSQL major version

PostGIS

Redis model

migration chain

gateway model

worker model
```

Separate:

```
database

secrets

storage

provider tenants/accounts

feature flags

recipient allowlists
```

---

# 76. Deployment

```
PR CI

→ merge

→ immutable image

→ staging deployment

→ migration

→ smoke

→ E2E

→ security verification

→ approval

→ backup

→ production canary

→ production smoke

→ monitored soak

→ controlled rollout
```

No deployment from a developer workstation.

---

# 77. Rollback

Every candidate includes:

```
previous image digest

schema compatibility

configuration rollback

rollback command

backup reference

verification steps
```

Prefer migrations compatible with previous application version.

---

# 78. Feature Activation

Deployment and capability activation are separate.

Example:

```
matching_code_deployed=true

matching_enabled=false
```

Activation requires:

```
staging certified

security approved

Ops ready

provider data ready

dependencies ready

monitoring ready
```

---
