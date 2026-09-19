# PR IMPLEMENTATION TEMPLATE

Every implementation PR must be independently reviewable.

## Scope

```
SCOPE=
NON_GOALS=
BASE_BRANCH=
BASE_SHA=
```

## Architecture

```
ARCHITECTURE_CHANGE=
ADR_REQUIRED=
```

## Database

```
MIGRATION_PREVIOUS_HEAD=
MIGRATION_NEW_HEAD=

EMPTY_DB_TO_HEAD=
CURRENT_HEAD_TO_NEW_HEAD=
SCHEMA_DRIFT=
```

## Domain

```
COMMANDS=
POLICIES=
STATE_MACHINES=
EVENTS=
```

## API

```
ENDPOINTS=
OPENAPI_STATUS=
```

## Security

```
AUTH_REQUIREMENTS=
PERMISSIONS=
RECORD_POLICIES=
CAPABILITIES=
```

## Reliability

```
IDEMPOTENCY=
CONCURRENCY=
AUDIT=
OUTBOX=
INBOX=
```

## Testing

```
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

FRONTEND_TESTS=
PLAYWRIGHT=
ACCESSIBILITY=
```

## Security scanning

```
DEPENDENCY_SCAN=
CONTAINER_SCAN=
SECRET_SCAN=
```

## Release

```
FINAL_SHA=

CAPABILITIES_ENABLED=

EXTERNAL_SENDS_ENABLED=

PRODUCTION_DB_TOUCHED=NO

SECRETS_EXPOSED=NO

KNOWN_RISKS=

ROLLBACK=

BLOCKERS=

NEXT_SAFE_ACTION=
```

Do not call the PR complete if required evidence is missing.

---

# FEATURE IMPLEMENTATION ORDER AFTER P0

Once P0\_FINAL passes:

```
01 Catalog

02 ProjectRequest

03 Provider Core

04 Provider Onboarding

05 Credentials

06 Availability

07 Matching

08 Opportunities

09 LeadConnection

10 Quotes

11 Conversations

12 Booking Bridge

13 Jobs

14 Reviews

15 Notifications

16 Disputes

17 Ops

18 Admin

19 Generated V2 frontend client

20 Customer frontend

21 Provider frontend

22 Worker frontend

23 Ops frontend

24 Admin frontend

25 Full staging vertical slice

26 Failure/security vertical slice

27 Canary

28 Controlled production activation
```

---

# MARKETPLACE DATABASE DOMAINS

Required core persistence eventually includes:

```
service questions/options/rules

project_requests
project_request_answers
project_request_attachments
project_request_status_history

provider/application/profile/member/worker data

credential_requirements
provider_credentials
credential_verifications
provider_documents

availability rules/exceptions

matching_runs
match_candidates
match_reasons

opportunities
opportunity_status_history

lead_connections

quotes
quote_versions
quote_line_items
quote_status_history

conversations
conversation_participants
messages
message_attachments
message_receipts

booking marketplace links

job_assignments
job_status_history
job_notes
job_evidence
job_additional_work

reviews
review dimensions/responses/moderation

disputes
dispute history/evidence/notes

notification_intents
notifications
notification_deliveries

operational_exceptions

external_identities
idempotency_records
integration_inbox
storage_objects
upload_sessions
```

Follow existing repository naming conventions.

Do not invent conflicting PostgreSQL schemas/namespaces.

---

# MATCHING RULES

Hard eligibility gates:

```
provider ACTIVE

service supported

geographic coverage

credentials valid

insurance valid where required

not suspended

qualified worker

availability

capacity

legal entity compatibility
```

Failing any required gate:

```
eligible=false
```

Suggested deterministic V1 score:

```
Availability                 20

Distance/service area        20

Verified rating              15

Completion rate              10

Opportunity acceptance       10

Response speed               10

Price competitiveness         5

Prior relationship            5

Platform quality              5
```

Store:

```
algorithm version

configuration snapshot

score components

reason codes

rank
```

for historical explainability.

---

# PROVIDER CREDENTIAL RULE

Matching fails closed if a required credential is:

```
missing

unverified

expired

revoked
```

Sensitive numbers encrypted.

Only safe summary/last-four data may be publicly projected.

---

# FRONTEND PAGE OWNERSHIP

Customer:

```
/
/services
/services/[slug]

/pros
/pros/[slug]

/request
/request/[id]

/requests
/requests/[id]

/messages/[conversationId]

/bookings/[id]

/jobs/[id]

/reviews/[jobId]

/disputes/[id]

/account/*
```

Provider:

```
/overview

/onboarding

/opportunities

/leads

/quotes

/messages

/schedule

/jobs

/customers

/workers

/services

/service-areas

/availability

/credentials

/reviews

/disputes

/analytics

/settings
```

Worker:

```
/worker

/worker/today

/worker/jobs/[id]

/worker/schedule

/worker/availability

/worker/credentials

/worker/profile
```

Ops:

```
/dashboard

/requests/[id]

/matching/[runId]

/opportunities

/jobs/[id]

/providers/[id]

/exceptions/[id]

/disputes/[id]

/integrations/[eventId]

/map

/analytics
```

Admin:

```
/dashboard

/provider-applications/[id]

/providers/[id]

/credentials/[id]

/users/[id]

/roles

/catalog

/features

/reviews

/disputes

/integrations

/audit

/system/health

/system/releases
```

---

# STAGING ACCEPTANCE SLICE

Exact production candidate must prove:

```
OIDC login

→ ProjectRequest

→ dynamic questionnaire

→ safe upload

→ submit

→ qualification

→ matching

→ Opportunity

→ provider acceptance

→ LeadConnection

→ conversation

→ Quote

→ customer acceptance

→ Booking

→ worker assignment

→ Job

→ completion

→ Verified Review
```

---

# FAILURE ACCEPTANCE SLICE

Also prove:

```
wrong issuer denied

wrong audience denied

cross-customer denied

cross-provider denied

unassigned worker denied

disabled capability denied

expired credential cannot match

suspended provider cannot match

duplicate ProjectRequest submit safe

duplicate Opportunity acceptance safe

duplicate Quote acceptance safe

duplicate webhook safe

invalid webhook signature denied

replay webhook denied

stale outbox worker cannot finalize

worker crash lease recovery works

middleware outage preserves business state

unsafe upload quarantined

payments unavailable while disabled
```

---

# FINAL RELEASE MANIFEST

Every release candidate produces:

```
FINAL_STATUS=

SOURCE_SHA=

IMAGE_DIGEST=

MIGRATION_HEAD=

CONFIG_CHECKSUM=

SBOM_DIGEST=

SIGNATURE_STATUS=

AUTHENTICATION_STATUS=

IDENTITY_STATUS=

AUTHORIZATION_STATUS=

CAPABILITY_STATUS=

IDEMPOTENCY_STATUS=

CONCURRENCY_STATUS=

AUDIT_STATUS=

OUTBOX_STATUS=

INBOX_STATUS=

WEBHOOK_STATUS=

STORAGE_STATUS=

NOTIFICATION_STATUS=

ADAPTER_STATUS=

FRONTEND_STATUS=

OPS_STATUS=

OBSERVABILITY_STATUS=

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

# CODEX IMPLEMENTATION DIRECTIVE

Reconcile the current repository against this package before making changes.

Preserve existing production-safe architecture and backwards compatibility.

Do not introduce duplicate identity systems, capability services, database schemas, domain aggregates, outbox systems, inbox systems, API clients or integration layers.

Use the existing canonical public capabilities endpoint and capability service.

Implement P0 in the specified sequence.

For each business mutation enforce, as applicable:

```
authentication

permission

record authorization

capability

valid state

idempotency

concurrency
```

Every high-value command must atomically commit:

```
business mutation
+
history
+
audit
+
idempotency completion
+
outbox
```

Outbound integrations use:

```
outbox
→ worker
→ adapter
→ external provider
```

Inbound integrations use:

```
verify
→ durable inbox
→ 202
→ worker
→ translator
→ authorized command
```

Do not call external systems directly from domain services.

Do not make CRM, middleware, email, SMS, workflow automation, business-verification providers, risk providers or payment providers authoritative for marketplace state.

Keep dangerous capabilities disabled until separately certified.

Every implementation step must be a separate, independently reviewable PR with the evidence block in this package.

Do not begin Catalog until:

```
P0_FINAL=PASS
```

Do not report:

```
PRODUCTION_READY=YES
```

unless all mandatory production gates pass on the exact candidate SHA.

Do not merge or deploy solely because code compiles or CI unit tests pass.

Never bypass required independent review, branch protections, staging certification, backup/restore evidence or production approval.
