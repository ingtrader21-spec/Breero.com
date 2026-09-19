# BREERO Marketplace V2 — P0 Production Foundation Implementation Contract

## Status

This document is a binding implementation contract for the P0 production foundation. It replaces the earlier long-form copy/paste code examples in this file.

The actual BREERO repository, accepted migrations, shared services, tests, OpenAPI artifact, and reviewed implementation PRs remain authoritative. Implementers must extend those components rather than create parallel infrastructure from this document.

```text
DOCUMENT_TYPE=IMPLEMENTATION_CONTRACT
RUNNABLE_CODE=NO
MARKETPLACE_V2=NO_GO
P0_FINAL=FAIL
PRODUCTION_READY=NO
CAPABILITY_ACTIVATION=NO
```

## Historical baseline recorded on 2026-08-26

The values below are historical context, not the current schema or implementation
status. Use `docs/architecture/CURRENT_SYSTEM.md`, repository `AGENTS.md`, and
fresh exact-head evidence to establish the accepted baseline and remaining P0
work. Do not restart completed authentication or authorization work from the
original branch sequence in this document.

```text
ACCEPTED_MAIN_SHA=8071572c90905d98894ab1a4cafe99a4178f7dd8
ALEMBIC_HEAD=017_provider_credentials
CURRENT_RELEASE_BOUNDARY=QUOTE_ONLY_OPERATOR_CONFIRMED_MANUAL_SCHEDULING
PAYMENTS_ENABLED=false
```

The accepted application is not a blank scaffold and is not the older request-only prototype. Every P0 branch starts from the latest accepted `main` and preserves the existing V1 contract unless a separately reviewed compatibility change says otherwise.

## Non-goals

P0 does not implement or activate:

```text
provider marketplace launch
matching
opportunities
paid leads
provider self-service
messaging
reviews
instant booking
automatic booking
automatic assignment
automatic confirmation
payments
refund execution
payouts
marketing
unrestricted email or SMS
unrestricted external automation
production deployment
```

Route, schema, model, configuration-key, mock, or documentation presence never activates a capability.

# 1. Dependency-ordered P0 branches

```text
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
be/marketplace-v2-p0-webhook-inbox
        ↓
be/marketplace-v2-p0-storage-uploads
        ↓
be/marketplace-v2-p0-operations-foundation
        ↓
be/marketplace-v2-p0-observability-deployment
```

A branch may be split further for reviewability. It must not pull a later domain or capability forward before its prerequisites pass.

# 2. Shared application boundaries

Extend the existing monorepo and FastAPI application. Expected ownership boundaries include:

```text
apps/api/app/api/v2/
apps/api/app/domains/authorization/
apps/api/app/domains/common/
apps/api/app/domains/capabilities/
apps/api/app/domains/integrations/
apps/api/app/domains/storage/
apps/api/app/integrations/
apps/api/app/workers/
apps/api/app/observability/
apps/api/tests/
```

Create a file only when it has a real responsibility. Do not create empty success routes, fake repositories, duplicate capability registries, duplicate error systems, or a second outbox/inbox implementation.

# 3. Principal and identity

Production human authentication uses OIDC Authorization Code + PKCE. Machine identities use approved client credentials.

Canonical issuer:

```text
https://auth.codestra.co/realms/codestra
```

Identity binding is immutable:

```text
(issuer, subject) → external_identity → local user → memberships → permissions → Principal
```

Email is profile data, not an identity key.

A server-constructed `Principal` may include:

```text
user_id
issuer
subject
tenant_id
legal_entity_ids
roles
permissions
provider_membership_ids
provider_ids
worker_id
machine_client_id
```

Browser-provided tenant, provider, worker, role, or permission values are never authoritative.

# 4. Authentication requirements

Validate at minimum:

```text
signature
algorithm
issuer
audience
azp where required
exp
nbf
iat
subject
kid
```

Discovery and JWKS behavior:

```text
process-wide bounded cache
unknown kid → refresh once → retry once
still invalid → deny
```

Production startup fails closed when authoritative OIDC configuration is absent. Local password/JWT authentication is unavailable in production.

Required negative tests include wrong issuer, wrong audience, wrong azp, disallowed algorithm, expired, not-yet-valid, malformed, missing token, unknown kid after refresh, and local-production-login denial.

# 5. Canonical permission names

The implementation must use one stable permission catalog across authorization policy, API registry, tests, documentation, seeds, and admin surfaces.

Canonical quote-decision permission:

```text
quote.accept
```

`quote.accept` covers the owning customer's authorized accept/decline decision command unless a later reviewed ADR deliberately separates those actions. Do not introduce `quote.decide` in parallel.

Other initial permission families are defined by `docs/marketplace-v2/04_SECURITY_AUTHORIZATION_MATRIX.md`.

# 6. Authorization and record policy

Every protected command/query requires:

```text
valid Principal
AND required permission
AND active tenant/legal-entity membership
AND aggregate-specific record policy
AND resource state permits operation
AND required capability is effective
AND command preconditions pass
```

Private cross-tenant, cross-customer, cross-provider, unmatched-provider, and unassigned-worker resources should return `404` where revealing existence would leak information.

Prefer authorized repository methods such as:

```text
project_request_for_customer(id, customer_id)
quote_for_provider(id, provider_id)
job_for_worker(id, worker_id)
```

over loading an arbitrary row and authorizing after exposure.

# 7. Command context

Construct `CommandContext` from authoritative request and Principal state:

```text
actor_id
issuer
subject
request_id
correlation_id
tenant_id
legal_entity_id
provider_id where applicable
worker_id where applicable
idempotency_key
ip address
user agent
```

Propagate it into audit, domain events, outbox/inbox records, integration requests, structured logs, and traces. Validate inbound request/correlation identifiers before reflecting them.

# 8. Domain events and transactions

A high-value command normally commits in one PostgreSQL transaction:

```text
business mutation
+ status/history
+ audit event
+ idempotency completion
+ transactional outbox event
```

No external HTTP/provider call belongs inside that transaction.

Domain-event identifiers and timestamps use per-instance factories, never import-time mutable/default values.

# 9. Idempotency model

Persist an idempotency record with at least:

```text
actor_key
operation
idempotency_key
request_hash
acquisition_token
status
resource_type
resource_id
response_code
response_json
created_at
updated_at
expires_at
```

Unique identity:

```text
(actor_key, operation, idempotency_key)
```

Supported states begin with:

```text
IN_PROGRESS
COMPLETED
FAILED_RETRYABLE
```

## 9.1 Acquire behavior

Acquire the record before business mutation or inside a savepoint that cannot roll back unrelated staged domain work.

Required algorithm:

1. Compute a canonical request hash.
2. Read the matching record with `FOR UPDATE`.
3. Compute `now` before evaluating expiration.
4. When an existing record has `expires_at <= now`, recycle that locked row atomically for the new request:
   - replace `request_hash`;
   - set `status=IN_PROGRESS`;
   - clear prior `resource_type`, `resource_id`, `response_code`, and `response_json`;
   - set fresh `expires_at`, `created_at`/generation metadata as designed, and `updated_at`;
   - replace `acquisition_token` with a fresh cryptographically random value that cannot equal any prior generation;
   - return a non-replay acquisition.
5. For a non-expired record:
   - same key + different hash → `409 IDEMPOTENCY_KEY_REUSED`;
   - same hash + `COMPLETED` → replay the recorded status/body;
   - same hash + active `IN_PROGRESS` → conflict/retry response;
   - retryable terminal state follows the documented retry policy.
6. When no row exists, insert `IN_PROGRESS` with a fresh expiry and a fresh cryptographically random `acquisition_token`.
7. Handle concurrent insert races through the unique constraint and a savepoint/re-read; do not call `session.rollback()` in a way that discards unrelated command state.

Expiration must have real behavior. It is not acceptable to keep replaying, conflicting, or reporting in-progress forever merely because a cleanup job has not deleted the row.

## 9.2 Idempotency completion

Completion, failure, and any replay-state mutation require the exact current `acquisition_token` and expected state in their update predicate. Completion records the authoritative resource and response in the same transaction as the command result. A stale owner whose record was recycled must update zero rows, must not complete or fail the newer generation, and must not commit a second business effect. Failed transactions must not leave a false completed response.

Mandatory tests:

```text
same key + same body replays
same key + different body conflicts
active in-progress conflicts
expired completed row is safely recycled
expired in-progress row is safely recycled according to policy
every first acquisition and recycle receives a distinct acquisition token
stale expired owner cannot complete or fail a recycled record
concurrent first insert has one owner
insert race does not roll back unrelated staged work
response replay preserves status/body
```

# 10. Optimistic concurrency

Version/ETag/If-Match applies to mutable high-value aggregates.

```text
stale If-Match → 412 PRECONDITION_FAILED
domain race/invariant conflict → 409 CONCURRENT_MODIFICATION
```

Use PostgreSQL constraints and row locks where an invariant needs true serialization. Mandatory race tests run against PostgreSQL, not SQLite substitutes.

# 11. Capability authority

Extend the existing capability service. The canonical public endpoint remains:

```text
GET /api/v1/public/capabilities
```

A V2 alias may exist only as a projection of the exact same service. It is not a second source of truth.

Effective capability requires all applicable dimensions:

```text
code available
AND environment configured
AND release flag enabled
AND dependencies ready
AND provider ready
AND environment policy approved
```

Missing, unreadable, false, or conflicting state fails closed. Every sensitive backend command checks capability independently of frontend visibility.

# 12. Transactional outbox

Extend the existing outbox and preserve its proven recovery behavior.

Required fields/semantics include:

```text
status
attempt_count
next_attempt_at
claimed_by
claim_token
claimed_at
lease_expires_at
processed_at
delivered_at
destination
correlation_id
causation_id
last_error_code
```

## 12.1 Claim eligibility

A row is claimable when either:

```text
A. status is PENDING / FAILED_RETRYABLE / RETRYING
   AND next_attempt_at <= now
   AND no live lease blocks the row

OR

B. status is PROCESSING
   AND lease_expires_at < now
```

Expired `PROCESSING` rows must be eligible for recovery. Omitting them strands events after a worker crash.

Claims use `SELECT ... FOR UPDATE SKIP LOCKED`, deterministic ordering, and a bounded batch.

## 12.2 Claim ownership

Every claim generation receives a fresh cryptographically random token, for example a new UUID:

```text
claimed_by = stable worker identity
claim_token = unique value generated for this specific claim attempt
```

Never use `worker_id` as `claim_token`. The same worker can reclaim an expired event while its old attempt is still running; a stable token would allow the stale attempt to finalize the newer claim.

For each claimed row:

```text
status = PROCESSING
claimed_by = worker_id
claim_token = fresh UUID
claimed_at = now
lease_expires_at = now + lease duration
```

## 12.3 Finalization and lease safety

Success, retry, terminal failure, and lease extension updates must require the exact current claim token and expected processing state.

Conceptual condition:

```text
WHERE id = :event_id
  AND status = 'PROCESSING'
  AND claim_token = :claim_token
```

A stale attempt that owns an older token updates zero rows and must not alter the newer claim.

Required behavior:

- lease extension uses the current token;
- provider delivery result is recorded separately from processing timestamps;
- retry/backoff is bounded and classified;
- unknown event types become visible terminal failures rather than infinite retries;
- disabled/unconfigured destinations park safely without false delivery;
- duplicate delivery is tolerated through downstream idempotency.

Mandatory tests:

```text
worker crash leaves PROCESSING row
expired PROCESSING row is reclaimed
reclaim generates a different token even for the same worker
stale old attempt cannot mark newer claim delivered
stale old attempt cannot reschedule newer claim
lease extension requires current token
concurrent workers claim each row once
retryable and terminal classification
unknown event terminal visibility
disabled destination parking
```

# 13. Durable inbox and webhooks

Inbound provider flow:

```text
provider request
→ provider-specific authentication/signature
→ timestamp/replay validation
→ durable inbox insert
→ 202 acknowledgement
→ worker claim
→ allowlisted translator
→ normal authorized domain command
```

Persist at least provider, external event ID, event type, schema version, raw/body hash, authentication metadata, payload or approved redacted form, status, attempts, stable `claimed_by` worker identity, per-claim `claim_token`, lease expiry, correlation, timestamps, and error code.

Unique identity:

```text
(provider, external_event_id)
```

Handle duplicate insert races through the database constraint. A duplicate event must have at most one business effect.

Every inbox claim and expired-lease reclaim receives a fresh cryptographically random `claim_token`, even when the same stable worker identity reclaims it. Heartbeat, success, retryable failure, and terminal finalization updates require the exact current token and expected processing state. A stale translator must update zero rows and cannot finalize, reschedule, or extend a newer claim.

Do not perform synchronous third-party business mutation in the webhook route.

Manual durable-inbox replay requires `integration.replay`; `integration.retry` never grants inbound-event replay. Mandatory tests include invalid signature, stale timestamp, replay, duplicate race, worker crash/lease recovery, out-of-order event, unknown event type, wrong tenant, translator rejection, retry-only replay denial, and manual replay authorization.

# 14. Provider adapters

Provider-specific code stays behind provider-neutral contracts.

Each adapter defines:

```text
configuration and secret references
timeout
retryable statuses/errors
idempotency mapping
correlation propagation
response classification
circuit/degraded behavior
reconciliation behavior
health semantics
```

Do not retry a mutation unless the provider or adapter guarantees idempotency. Do not hardwire disabled optional providers into core readiness.

# 15. Private object storage and uploads

Required storage states begin with:

```text
PENDING_UPLOAD
UPLOADED
SCANNING
CLEAN
QUARANTINED
REJECTED
DELETED
```

Rules:

- private bucket/container only;
- short-lived signed upload/download access;
- purpose-specific size and MIME allowlists;
- checksum/size verification after upload;
- asynchronous malware scan;
- object unavailable to business workflows before `CLEAN`;
- authorization tied to owner/provider/job/credential/dispute policy;
- cleanup for abandoned sessions and rejected/quarantined content;
- retention/deletion/audit behavior defined;
- permanent public URLs forbidden.

# 16. Notifications and external communication

Notification intent/state belongs to BREERO. Klyrow/Telnexa/other providers are transports.

Default posture:

```text
unrestricted_email=false
unrestricted_sms=false
marketing=false
external_automation=false
```

Every future send requires purpose, recipient authorization, consent/suppression policy, template/version, idempotency, rate limits, outbox delivery, verified callback through inbox, and failure/operational visibility.

# 17. Operational exceptions

Create first-class operational exception state for terminal integration failures, reconciliation discrepancies, unassigned/late work, credential expiration, storage quarantine, and other recoverable launch conditions.

Authorized operations may acknowledge, assign, note, retry where valid, and resolve with reason. Manual retry/replay follows normal permission, capability, idempotency, audit, and claim-safety rules.

# 18. Observability

Provide:

```text
validated request/correlation IDs
structured logs
metrics
traces
queue depth and oldest age
PROCESSING lease age
inbox/outbox retry and terminal counts
worker heartbeat
provider latency/error/circuit state
operational exception backlog
```

Logs, metrics, traces, audit, and events must not expose secrets or unrestricted PII.

# 19. Health and version endpoints

Required endpoints distinguish:

```text
liveness
readiness
release/version identity
```

Readiness verifies only dependencies required for the currently effective release. Disabled optional providers do not make the core API unready.

Release identity includes source SHA, image digest, migration head, and approved configuration/capability snapshot without secret values.

# 20. Backup, restore, deployment, and rollback

Before production readiness:

- encrypted dated database/object/config backup coverage;
- isolated restore rehearsal with integrity and application smoke evidence;
- measured RTO/RPO;
- immutable digest-pinned images;
- migration ordering and compatibility boundary;
- canary/abort thresholds;
- prior immutable rollback artifacts;
- data-safe rollback or forward-fix decision tree;
- named operator and approval/change record.

Scripts must never print passwords or run destructive restore operations against production.

# 21. CI contract

Every applicable implementation PR runs against PostgreSQL/PostGIS and includes:

```text
frozen dependency install
lint/format policy
compile/type checks
unit/domain tests
PostgreSQL/PostGIS integration tests
migration upgrade and supported-path evidence
migration/OpenAPI drift checks
negative authentication/authorization tests
idempotency/concurrency race tests
outbox/inbox lease and duplicate tests
storage/webhook security tests
dependency/secret/container scans as applicable
SBOM/provenance evidence as required
```

Frontend-affecting contracts also require lint, typecheck, tests, production build, API contract verification, accessibility/responsive checks, and relevant Playwright E2E.

Required status contexts must be unique and unambiguous. Repository issue #45 tracks the current `quality`-context governance defect.

# 22. Minimum P0 test inventory

```text
test_oidc_wrong_issuer_denied
test_oidc_wrong_audience_denied
test_oidc_unknown_kid_refresh_then_denied
test_local_production_auth_denied
test_external_identity_uses_issuer_subject
test_cross_tenant_denied
test_customer_cannot_read_other_customer_request
test_provider_cannot_read_other_provider_opportunity
test_worker_cannot_execute_unassigned_job
test_disabled_capability_rejects_command
test_idempotency_same_key_same_body_replays
test_idempotency_same_key_different_body_conflicts
test_idempotency_expired_record_recycles
test_idempotency_acquisition_uses_fresh_generation_token
test_stale_idempotency_owner_cannot_complete_recycled_record
test_concurrent_command_has_one_authoritative_effect
test_outbox_worker_reclaims_stale_processing_lease
test_outbox_reclaim_uses_fresh_claim_token
test_stale_outbox_attempt_cannot_finalize_new_claim
test_disabled_integration_parks_event
test_inbox_duplicate_event_has_one_business_effect
test_inbox_reclaim_uses_fresh_claim_token
test_stale_inbox_translator_cannot_finalize_new_claim
test_webhook_invalid_signature_denied
test_webhook_timestamp_replay_denied
test_upload_wrong_content_type_rejected
test_upload_unavailable_before_clean_scan
test_backup_restore_migration_smoke
```

# 23. P0 completion gate

Do not begin Catalog or later Marketplace V2 domains until:

```text
P0_API_FOUNDATION=PASS
P0_AUTHENTICATION=PASS
P0_IDENTITY=PASS
P0_AUTHORIZATION=PASS
P0_CAPABILITIES=PASS
P0_IDEMPOTENCY=PASS
P0_CONCURRENCY=PASS
P0_AUDIT=PASS
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

`P0_DEPLOYABILITY=PASS` means the exact foundation candidate is reproducibly deployable and rehearsed in isolated staging. It does not authorize production deployment or Marketplace V2 capability activation.

# 24. Vendor/environment-specific evidence

The following cannot be certified from repository code alone:

```text
Keycloak production client configuration
Codestra service credentials and mTLS
Klyrow service authorization
Telnexa service authorization
Odoo staging/production service identity
approved n8n workflow IDs
object-storage credentials and policy
malware-scanner configuration
geocoder account/policy
payment-provider account when later in scope
DNS/TLS/firewall/private routing
backup destination and retention
monitoring/alert destinations
```

Use mounted/managed secret references. Never commit or log secret values.

# 25. Review evidence

Every P0 implementation PR reports:

```text
starting main SHA
final exact head SHA
commit inventory
files/domains/contracts changed
migration head and upgrade/rollback evidence
permission and capability changes
OpenAPI/client changes
exact tests and CI run IDs
staging or environment evidence where applicable
unresolved risks
explicit statement that no capability was activated
```

CI green is necessary but not sufficient. Independent review, resolved threads, branch/ruleset gates, and exact-head evidence remain mandatory.
