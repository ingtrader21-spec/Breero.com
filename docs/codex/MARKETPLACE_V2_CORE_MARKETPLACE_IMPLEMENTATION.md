# BREERO Marketplace V2

# Part 2 — Core Marketplace Implementation

## Status

This document begins only after the complete P0 production foundation is green.

Required foundation before this work starts:

```text
API V2 foundation
OIDC authentication
issuer + subject identity binding
record-level authorization
canonical capability enforcement
transactional idempotency
optimistic concurrency
audit
transactional outbox
webhook inbox
storage/upload foundation
observability baseline
```

Do not rebuild those primitives inside feature domains.

## 1. Implementation sequence

Use this dependency order:

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
```

Recommended backend branches:

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

Create one draft PR per branch. Create each branch from the latest merged target only when its dependencies are green.

## 2. Shared domain conventions

Each domain should look approximately like:

```text
apps/api/app/domains/<domain>/

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

Only create files that have real responsibilities.

Every state-changing domain command follows:

```text
Load authorized aggregate
        ↓
Validate capability
        ↓
Validate policy
        ↓
Validate state transition
        ↓
Acquire/verify idempotency
        ↓
Apply mutation
        ↓
Append history
        ↓
Append audit
        ↓
Append domain/outbox event
        ↓
Complete idempotency
        ↓
COMMIT
```

## 3. Catalog domain

Catalog defines what BREERO can service and what information is required from the customer. Do not embed service-specific questions in frontend code.

Reuse existing services/categories where possible. Add only missing concepts:

```text
service_questions
service_question_options
service_question_rules
```

### service_questions

```text
id UUID PK
service_id UUID FK
key VARCHAR
label VARCHAR
help_text TEXT NULL
question_type VARCHAR
required BOOLEAN
sort_order INTEGER
validation_json JSONB
active BOOLEAN
created_at
updated_at

UNIQUE(service_id, key)
```

Question types:

```text
TEXT
TEXTAREA
BOOLEAN
NUMBER
SINGLE_SELECT
MULTI_SELECT
DATE
TIME
PHOTO
```

### service_question_options

```text
id UUID PK
question_id UUID FK
value VARCHAR
label VARCHAR
sort_order INTEGER
active BOOLEAN
```

### service_question_rules

```text
id UUID PK
service_id UUID FK
source_question_id UUID FK
operator VARCHAR
expected_value_json JSONB
target_question_id UUID FK
action VARCHAR
```

Rule actions are `SHOW`, `HIDE`, `REQUIRE`, and `OPTIONAL`.

## 4. Catalog API

```http
GET /api/v2/catalog/categories
GET /api/v2/catalog/categories/{slug}
GET /api/v2/catalog/services
GET /api/v2/catalog/services/{slug}
GET /api/v2/catalog/services/{id}/questions

POST  /api/v2/admin/catalog/categories
PATCH /api/v2/admin/catalog/categories/{id}
POST  /api/v2/admin/catalog/services
PATCH /api/v2/admin/catalog/services/{id}
POST   /api/v2/admin/catalog/services/{id}/questions
PATCH  /api/v2/admin/catalog/questions/{id}
DELETE /api/v2/admin/catalog/questions/{id}
```

The server validates question requirements during ProjectRequest submission. Frontend validation is supplemental.

## 5. ProjectRequest domain

`ProjectRequest` is the canonical representation of customer demand. Never create Booking before the request progresses through the appropriate marketplace workflow.

Tables:

```text
project_requests
project_request_answers
project_request_attachments
project_request_status_history
```

### project_requests

```text
id UUID PK
reference VARCHAR UNIQUE
customer_id UUID NULL
property_id UUID NULL
service_id UUID NOT NULL
address_id UUID NOT NULL
legal_entity_id UUID NULL
status VARCHAR NOT NULL
fulfillment_mode VARCHAR NULL
title VARCHAR NULL
description TEXT
urgency VARCHAR
budget_min_minor BIGINT NULL
budget_max_minor BIGINT NULL
currency CHAR(3)
preferred_start_at TIMESTAMPTZ NULL
preferred_end_at TIMESTAMPTZ NULL
source VARCHAR
source_campaign VARCHAR NULL
submitted_at TIMESTAMPTZ NULL
expires_at TIMESTAMPTZ NULL
cancelled_at TIMESTAMPTZ NULL
version INTEGER NOT NULL DEFAULT 1
created_at
updated_at
```

States:

```text
DRAFT
SUBMITTED
QUALIFYING
MATCHING
MATCHED
QUOTING
BOOKED
CANCELLED
EXPIRED
UNSERVICEABLE
```

Fulfillment modes:

```text
INSTANT_BOOK
QUOTE_REQUIRED
MANUAL_DISPATCH
UNSERVICEABLE
```

## 6. ProjectRequest state machine

```text
DRAFT
 ├── SUBMITTED
 └── CANCELLED

SUBMITTED
 ├── QUALIFYING
 ├── CANCELLED
 └── UNSERVICEABLE

QUALIFYING
 ├── MATCHING
 ├── UNSERVICEABLE
 └── CANCELLED

MATCHING
 ├── MATCHED
 ├── UNSERVICEABLE
 └── CANCELLED

MATCHED
 ├── QUOTING
 ├── BOOKED
 └── CANCELLED

QUOTING
 ├── BOOKED
 ├── EXPIRED
 └── CANCELLED
```

Never directly mutate `status` outside the domain service.

## 7. ProjectRequest commands

```text
CreateProjectRequest
UpdateProjectRequest
SaveProjectAnswer
AttachProjectFile
RemoveProjectFile
SubmitProjectRequest
QualifyProjectRequest
MarkProjectUnserviceable
CancelProjectRequest
ExpireProjectRequest
```

Submission requires:

```text
request is DRAFT
service active
address valid/serviceable enough to continue
all required visible questions answered
required attachments clean
timing valid
customer owns request
request_intake capability enabled
```

## 8. ProjectRequest API

```http
POST   /api/v2/project-requests
GET    /api/v2/project-requests/{id}
PATCH  /api/v2/project-requests/{id}
PUT    /api/v2/project-requests/{id}/answers/{questionId}
DELETE /api/v2/project-requests/{id}/answers/{questionId}
POST   /api/v2/project-requests/{id}/attachments
DELETE /api/v2/project-requests/{id}/attachments/{attachmentId}
POST   /api/v2/project-requests/{id}/submit
POST   /api/v2/project-requests/{id}/cancel

GET /api/v2/customer/project-requests

GET  /api/v2/ops/project-requests
GET  /api/v2/ops/project-requests/{id}
POST /api/v2/ops/project-requests/{id}/qualify
POST /api/v2/ops/project-requests/{id}/mark-unserviceable
```

## 9. ProjectRequest events

```text
project_request.created.v1
project_request.updated.v1
project_request.submitted.v1
project_request.qualified.v1
project_request.unserviceable.v1
project_request.cancelled.v1
project_request.expired.v1
```

## 10. Provider Core

Extend the existing vendor/provider model rather than creating duplicate concepts.

```text
Provider Organization
Provider Profile
Provider Member
Provider Worker
Provider Service
Provider Service Area
Provider Gallery
```

Provider states:

```text
DRAFT
PENDING_REVIEW
ACTIVE
SUSPENDED
REJECTED
CLOSED
```

## 11. Provider profile

The public-safe projection includes provider ID, display name, slug, headline, description, years in business, logo, cover, services, service-area summary, rating average/count, verified-job count, response-time metric, trust badges, and public profile state.

Never expose private phone/email, credential or identity documents, bank information, internal quality notes, or suspension investigation details.

## 12. Provider APIs

```http
GET /api/v2/providers
GET /api/v2/providers/{slug}
GET /api/v2/providers/{slug}/services
GET /api/v2/providers/{slug}/reviews
GET /api/v2/providers/{slug}/service-area
GET /api/v2/providers/{slug}/availability-summary

GET   /api/v2/partner/profile
PATCH /api/v2/partner/profile
GET   /api/v2/partner/services
PUT   /api/v2/partner/services
GET   /api/v2/partner/service-areas
POST  /api/v2/partner/service-areas
PATCH /api/v2/partner/service-areas/{id}
DELETE /api/v2/partner/service-areas/{id}
GET   /api/v2/partner/workers
POST  /api/v2/partner/workers
GET   /api/v2/partner/workers/{id}
PATCH /api/v2/partner/workers/{id}
```

## 13. Provider onboarding

Tables: `provider_applications` and `provider_application_status_history`.

States: `DRAFT`, `SUBMITTED`, `UNDER_REVIEW`, `NEEDS_INFORMATION`, `APPROVED`, and `REJECTED`.

```http
POST /api/v2/public/provider-applications
GET   /api/v2/partner/onboarding
PATCH /api/v2/partner/onboarding
POST  /api/v2/partner/onboarding/submit
GET   /api/v2/admin/provider-applications
GET   /api/v2/admin/provider-applications/{id}
POST  /api/v2/admin/provider-applications/{id}/request-information
POST  /api/v2/admin/provider-applications/{id}/approve
POST  /api/v2/admin/provider-applications/{id}/reject
```

Submission generates `provider_application.submitted.v1`.

## 14. Credentials and trust

Tables:

```text
credential_requirements
provider_credentials
credential_verifications
provider_documents
```

Credential subjects are `PROVIDER` and `WORKER`. States are `PENDING`, `VERIFIED`, `REJECTED`, `EXPIRED`, and `REVOKED`. Requirements may depend on service, jurisdiction, and provider/worker type.

Matching must fail closed: a required credential that is missing, expired, revoked, or unverified makes the provider ineligible.

## 15. Credentials API

```http
GET   /api/v2/partner/credentials
POST  /api/v2/partner/credentials
GET   /api/v2/partner/credentials/{id}
PATCH /api/v2/partner/credentials/{id}
POST  /api/v2/partner/credentials/{id}/documents

GET  /api/v2/admin/credentials
GET  /api/v2/admin/credentials/{id}
POST /api/v2/admin/credentials/{id}/verify
POST /api/v2/admin/credentials/{id}/reject
POST /api/v2/admin/credentials/{id}/revoke
```

Events:

```text
credential.submitted.v1
credential.verified.v1
credential.rejected.v1
credential.expiring.v1
credential.expired.v1
credential.revoked.v1
```

## 16. Provider availability

Tables: `provider_availability_rules` and `provider_availability_exceptions`.

Rules support provider or worker, weekday, multiple time windows, capacity, timezone, effective date, and expiration date. Exceptions support a specific date, unavailable flag, custom window, capacity override, and reason.

## 17. Availability API

```http
GET    /api/v2/partner/availability
PUT    /api/v2/partner/availability
POST   /api/v2/partner/availability/exceptions
PATCH  /api/v2/partner/availability/exceptions/{id}
DELETE /api/v2/partner/availability/exceptions/{id}

GET /api/v2/worker/availability
PUT /api/v2/worker/availability

GET /api/v2/providers/{slug}/availability-summary
GET /api/v2/project-requests/{id}/availability
```

## 18. Matching domain

Tables: `matching_runs`, `match_candidates`, and `match_reasons`.

`matching_runs` stores ProjectRequest, algorithm, algorithm version, configuration snapshot, status, start/completion timestamps, and initiator. A candidate stores provider, eligibility, rank, final score, distance, and score components. A reason stores eligibility gate, reason code, pass/fail, score delta, and safe diagnostic details.

## 19. Matching eligibility

Hard gates:

```text
Provider ACTIVE
Service supported
Request location inside provider area
Required credentials valid
Insurance valid where applicable
Provider not suspended
Qualified worker exists
Availability exists
Capacity exists
Legal entity compatible
```

Failing any required gate sets `eligible = false`. Ranking can never override an eligibility failure.

## 20. Matching V1 score

Use deterministic configuration and store the exact configuration used in every run.

```text
Availability               20
Distance                   20
Verified rating            15
Completion rate            10
Opportunity acceptance     10
Response speed             10
Price competitiveness       5
Prior relationship          5
BREERO quality score        5
```

No ML in V1.

## 21. Matching commands

```text
StartMatching
EvaluateCandidate
CompleteMatching
ReRunMatching
```

Matching must be repeatable from stored inputs and configuration.

## 22. Matching API

```http
POST /api/v2/ops/project-requests/{id}/matching-runs
GET  /api/v2/ops/matching-runs/{id}
GET  /api/v2/ops/matching-runs/{id}/candidates
GET  /api/v2/ops/matching-runs/{id}/candidates/{candidateId}

GET /api/v2/project-requests/{id}/matches
```

Never expose internal risk or quality reasons through the customer-safe endpoint.

## 23. Matching events

```text
matching.started.v1
matching.completed.v1
matching.no_candidates.v1
```

`matching.no_candidates.v1` creates an operational exception.

## 24. Opportunity domain

Tables: `opportunities` and `opportunity_status_history`.

States: `SENT`, `VIEWED`, `ACCEPTED`, `DECLINED`, `EXPIRED`, and `WITHDRAWN`.

An opportunity belongs to exactly one provider. Active provider membership is required, the provider must remain eligible enough to accept, the opportunity must not be expired, and duplicate acceptance must be idempotent.

## 25. Opportunity commands

```text
CreateOpportunity
ViewOpportunity
AcceptOpportunity
DeclineOpportunity
ExpireOpportunity
WithdrawOpportunity
```

Acceptance creates exactly one `LeadConnection`.

## 26. Provider opportunity API

```http
GET  /api/v2/partner/opportunities
GET  /api/v2/partner/opportunities/{id}
POST /api/v2/partner/opportunities/{id}/view
POST /api/v2/partner/opportunities/{id}/accept
POST /api/v2/partner/opportunities/{id}/decline

POST /api/v2/ops/project-requests/{id}/opportunities
POST /api/v2/ops/opportunities/{id}/withdraw
```

## 27. LeadConnection domain

`LeadConnection` represents the authorized marketplace relationship. It includes ProjectRequest, Provider, Opportunity, status, customer contact-access level, connected timestamp, and closed timestamp.

Contact access levels are `NONE`, `MASKED`, and `AUTHORIZED`. The connection authorizes conversation, quotes, and only the appropriate customer/request information.

## 28. Lead API

```http
GET /api/v2/partner/leads
GET /api/v2/partner/leads/{id}
```

There is no public LeadConnection endpoint.

## 29. Quotes

Tables:

```text
quotes
quote_versions
quote_line_items
quote_status_history
```

States: `DRAFT`, `SENT`, `REVISED`, `ACCEPTED`, `DECLINED`, `EXPIRED`, and `WITHDRAWN`.

A sent version is immutable. Revision creates a new draft version; it never edits the sent version.

## 30. Quote line item types

```text
LABOR
MATERIAL
TRAVEL
PERMIT
OTHER
DISCOUNT
```

Store money in minor units. Never use float.

## 31. Quote commands

```text
CreateQuote
UpdateDraftQuote
SendQuote
CreateQuoteRevision
WithdrawQuote
AcceptQuote
DeclineQuote
ExpireQuote
```

`AcceptQuote` must be concurrency-safe and idempotent.

## 32. Quote API

```http
GET   /api/v2/partner/quotes
GET   /api/v2/partner/quotes/{id}
POST  /api/v2/partner/project-requests/{id}/quotes
PATCH /api/v2/partner/quotes/{id}
POST  /api/v2/partner/quotes/{id}/send
POST  /api/v2/partner/quotes/{id}/revise
POST  /api/v2/partner/quotes/{id}/withdraw

GET  /api/v2/project-requests/{id}/quotes
GET  /api/v2/quotes/{id}
POST /api/v2/quotes/{id}/accept
POST /api/v2/quotes/{id}/decline
```

## 33. Quote events

```text
quote.created.v1
quote.sent.v1
quote.revised.v1
quote.accepted.v1
quote.declined.v1
quote.expired.v1
quote.withdrawn.v1
```

## 34. Messaging domain

Tables:

```text
conversations
conversation_participants
messages
message_attachments
message_receipts
```

A conversation normally relates to a ProjectRequest and LeadConnection, and optionally a Booking and Job.

## 35. Message types

```text
TEXT
IMAGE
DOCUMENT
QUOTE
APPOINTMENT_PROPOSAL
SYSTEM
```

Attachments must already be `CLEAN` before message publication.

## 36. Messaging authorization

Every conversation query must prove an authenticated user, active conversation participation, and a still-valid provider/customer relationship. Never perform a direct conversation lookup by ID without participant filtering.

## 37. Messaging API

```http
GET  /api/v2/conversations
GET  /api/v2/conversations/{id}
GET  /api/v2/conversations/{id}/messages
POST /api/v2/conversations/{id}/messages
POST /api/v2/conversations/{id}/attachments
POST /api/v2/conversations/{id}/read
```

## 38. Messaging events

```text
conversation.created.v1
conversation.message_sent.v1
conversation.message_read.v1
```

Notification policy consumes `message_sent`; the domain never calls Klyrow or Telnexa directly.

## 39. Booking bridge

Do not replace the existing Booking aggregate. Extend it additively with nullable `project_request_id`, `accepted_quote_id`, `provider_id`, and `worker_id` relationships. Legacy records remain valid.

## 40. Booking creation rules

A Booking may originate from an accepted quote, approved instant-book flow, or Ops/manual dispatch. Booking must never represent provider search, qualification, or quote negotiation.

## 41. Booking API

```http
GET  /api/v2/bookings/{id}
GET  /api/v2/bookings/{id}/timeline
POST /api/v2/bookings/{id}/confirm
POST /api/v2/bookings/{id}/reschedule-request
POST /api/v2/bookings/{id}/cancel
```

When instant booking is disabled, customer timing remains requested/preferred until server-confirmed.

## 42. Job domain

States:

```text
CREATED
ASSIGNED
EN_ROUTE
ARRIVED
DIAGNOSING
AWAITING_APPROVAL
IN_PROGRESS
COMPLETED
CANCELLED
```

Tables/history:

```text
job_assignments
job_status_history
job_notes
job_evidence
job_additional_work
```

Assignment history is append-only.

## 43. Job commands

```text
CreateJob
AssignJob
ReassignJob
MarkEnRoute
MarkArrived
StartDiagnosis
RequestAdditionalWork
ApproveAdditionalWork
StartJob
CompleteJob
CancelJob
```

Every transition belongs to `JobStateMachine`.

## 44. Job API

```http
GET  /api/v2/jobs/{id}
GET  /api/v2/jobs/{id}/timeline
POST /api/v2/jobs/{id}/en-route
POST /api/v2/jobs/{id}/arrive
POST /api/v2/jobs/{id}/start
POST /api/v2/jobs/{id}/complete
POST /api/v2/jobs/{id}/notes
POST /api/v2/jobs/{id}/evidence
POST /api/v2/jobs/{id}/additional-work

POST /api/v2/ops/jobs/{id}/assign
POST /api/v2/ops/jobs/{id}/reassign
POST /api/v2/ops/jobs/{id}/cancel
```

## 45. Worker API

```http
GET  /api/v2/worker/profile
GET  /api/v2/worker/jobs
GET  /api/v2/worker/jobs/{id}
POST /api/v2/worker/jobs/{id}/en-route
POST /api/v2/worker/jobs/{id}/arrive
POST /api/v2/worker/jobs/{id}/start
POST /api/v2/worker/jobs/{id}/complete
POST /api/v2/worker/jobs/{id}/notes
POST /api/v2/worker/jobs/{id}/evidence
```

Worker queries must filter by worker assignment.

## 46. Reviews

Tables: `reviews`, `review_dimensions`, `review_responses`, and `review_moderation`.

Eligibility requires `Job.status == COMPLETED`, the customer owns the originating ProjectRequest, and only one active review exists per job.

Dimensions: `OVERALL`, `QUALITY`, `COMMUNICATION`, `TIMELINESS`, and `VALUE`.

## 47. Review API

```http
POST /api/v2/jobs/{id}/review
GET  /api/v2/reviews/{id}
GET  /api/v2/providers/{slug}/reviews
GET  /api/v2/partner/reviews
POST /api/v2/partner/reviews/{id}/response
POST /api/v2/admin/reviews/{id}/moderate
```

Public reviews display `Verified Breero Job` when applicable.

## 48. Notification domain

Marketplace services never send communications directly.

```text
Domain Event
    ↓
NotificationPolicy
    ↓
NotificationIntent
    ↓
Preferences / consent
    ↓
IN_APP / EMAIL / SMS
```

Tables: `notification_intents`, `notifications`, and `notification_deliveries`.

## 49. Notification examples

For `quote.sent.v1`, create in-app notification when the account is active, transactional email when permitted, and SMS only when transactional SMS is permitted and the capability is enabled.

For `job.en_route.v1`, use in-app and optional SMS. For `credential.expiring.v1`, use provider in-app and transactional email.

## 50. Disputes

Add disputes before payment activation.

Tables: `disputes`, `dispute_status_history`, `dispute_notes`, and `dispute_evidence`.

States: `OPEN`, `UNDER_REVIEW`, `WAITING_CUSTOMER`, `WAITING_PROVIDER`, `RESOLVED`, `REJECTED`, and `CLOSED`.

## 51. Dispute API

```http
POST /api/v2/jobs/{id}/disputes
GET  /api/v2/customer/disputes
GET  /api/v2/customer/disputes/{id}

GET  /api/v2/partner/disputes
GET  /api/v2/partner/disputes/{id}
POST /api/v2/partner/disputes/{id}/respond

GET  /api/v2/ops/disputes
GET  /api/v2/ops/disputes/{id}
POST /api/v2/ops/disputes/{id}/request-information
POST /api/v2/ops/disputes/{id}/resolve
```

## 52. Operational exceptions

Automatically create an exception for zero matches, provider response overdue, stale opportunity, overdue quote, expiring/expired credential, unassigned or late job, terminal integration failure, and terminal webhook-processing failure.

Ops must not need SQL access to recover normal marketplace failures.

## 53. Domain test pattern

Every state machine gets explicit allowed and denied transition tests.

```python
def test_sent_quote_can_be_accepted():
    machine.require_transition("SENT", "ACCEPTED")


def test_accepted_quote_cannot_return_to_draft():
    with pytest.raises(DomainError):
        machine.require_transition("ACCEPTED", "DRAFT")
```

## 54. Authorization tests

Required negative tests:

```text
Customer A cannot access Customer B ProjectRequest
Provider A cannot access Provider B Opportunity
Provider A cannot access Provider B LeadConnection
Provider A cannot access Provider B Quote
Provider A cannot access Provider B Conversation
Provider A cannot access Provider B Job
Worker cannot access unassigned Job
Suspended provider cannot accept Opportunity
Expired credential provider cannot match
```

## 55. Concurrency tests

Use real PostgreSQL for simultaneous ProjectRequest submission, Opportunity acceptance, Quote acceptance, Job assignment, and Review creation.

Expected result:

```text
one business result
safe replay/conflict for the rest
```

## 56. Marketplace integration test

The first vertical slice proves:

```text
Customer
→ creates ProjectRequest
→ completes questions
→ submits
→ qualification
→ matching
→ eligible providers
→ Opportunity

Provider
→ accepts
→ LeadConnection
→ Conversation
→ Quote

Customer
→ accepts
→ Booking

Ops/provider
→ assignment

Worker
→ Job
→ Completed

Customer
→ Verified Review
```

Run against real PostgreSQL, real PostGIS, real migrations, and middleware adapters in safe/fake mode.

## 57. Marketplace failure integration test

Prove:

```text
zero eligible provider → Ops exception
expired credential → provider not matched
Opportunity expired → acceptance denied
Quote expired → acceptance denied
duplicate Opportunity accept → one LeadConnection
duplicate Quote accept → one Booking
Provider A cross-resource access → denied
Customer A cross-resource access → denied
middleware unavailable → business state preserved
payments disabled → no payment command available
```

## 58. Definition of Core Marketplace Complete

Part 2 is complete only when:

```text
Catalog is dynamic
ProjectRequest is canonical demand
Provider profiles work
credentials affect eligibility
availability affects eligibility
matching is deterministic and explainable
Opportunities are provider-specific
LeadConnection controls information disclosure
quotes are versioned
messaging is first-class
Booking is downstream
Jobs use explicit state transitions
reviews require completed jobs
notifications derive from events
disputes exist
Ops can recover exceptions
all important commands are audited/idempotent
all critical authorization tests pass
```

Do not activate payments as part of this phase.
