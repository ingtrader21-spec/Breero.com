# BREERO Marketplace V2 — Production Hardening Governance

## Status

This document is a **binding companion** to `00_PRODUCTION_BLUEPRINT.md` for Marketplace V2 production implementation. It strengthens governance, security boundaries, failure-mode handling, financial controls, and readiness proof. It does not enable any capability, authorize deployment, or declare production readiness.

Current status remains:

```text
REQUEST_ONLY_V1=PARTIAL
MARKETPLACE_V2=NO_GO
PRODUCTION_READY=NO
P0_FINAL=FAIL
```

Payments, payouts, paid leads, automatic assignment, automatic confirmation, unrestricted messaging, marketing, provider self-service, and every other dangerous capability remain disabled until their own activation gate passes.

## Non-bypassable production transition rule

> **No production-sensitive state transition may be possible through a route, worker, webhook, CRM action, workflow, provider callback, scheduled job, retry tool, support tool, or administrator surface unless it enters the same typed command → authentication → authorization → policy → state machine → capability gate → idempotency/concurrency → audit → transactional outbox path.**

External provider calls are never allowed inside the authoritative database transaction. Provider callbacks must enter through the durable inbox and translate to authorized commands.

---

# 1. Explicit threat model

The binding threat model is `11_THREAT_MODEL.md`.

It must cover at minimum:

- customer account takeover;
- provider owner/manager account takeover;
- worker account takeover;
- cross-customer and cross-provider data access;
- administrator privilege escalation;
- OIDC token/session theft;
- webhook forgery and replay;
- machine/provider credential theft;
- malicious document upload;
- PII exfiltration;
- insider abuse;
- fraudulent payment/refund/payout action;
- duplicate payment/refund/payout;
- duplicate provider/lead/opportunity side effects;
- Odoo compromise;
- n8n compromise;
- Codestra/Kong/middleware compromise;
- Redis compromise;
- object-storage exposure;
- database credential theft;
- dependency/build/supply-chain compromise.

Each threat records: asset, attacker, attack path, preventive control, detection, response, and residual risk.

---

# 2. Data-classification policy

The binding classification policy is `12_DATA_CLASSIFICATION.md`.

Classes:

```text
PUBLIC
INTERNAL
CONFIDENTIAL
RESTRICTED
HIGHLY_RESTRICTED
```

Each class defines:

- who may see it;
- where it may be stored;
- where it may be logged;
- whether it may be projected to Odoo/Codestra/n8n;
- retention;
- encryption;
- backup handling;
- export rules.

Raw secrets, payment credentials/tokens, identity secrets, sensitive verification documents, and highly sensitive customer/provider data must never be copied into CRM, workflow, analytics, frontend build variables, logs, or durable event payloads unless explicitly approved by the classification policy.

---

# 3. Explicit system-of-record matrix

The binding source-of-truth matrix is `13_SYSTEM_OF_RECORD_MATRIX.md`.

BREERO PostgreSQL/PostGIS remains authoritative for marketplace business state. Odoo remains CRM workflow/projection only. Codestra/Kong/middleware remains integration transport/control plane only. n8n remains allowlisted workflow execution only. Redis remains disposable/derived infrastructure state only.

A downstream system must never silently become authoritative because it happens to contain a copy of data.

---

# 4. Break-glass access

Never define an unrestricted role equivalent to:

```text
ADMIN = *
SUPER_ADMIN = *
```

Emergency elevation must use a dedicated `BREAK_GLASS` capability/role with:

- an explicit emergency reason;
- strong MFA/re-authentication;
- short TTL;
- explicit approval where feasible;
- least-privilege permission bundle;
- full audit trail;
- security/operations alert;
- automatic expiration;
- post-use review.

Example:

```text
Emergency access to HIGHLY_RESTRICTED customer/provider data
→ 30-minute elevation
→ reason required
→ elevated actions separately tagged in audit
→ automatic revocation
```

Break-glass must not bypass command, policy, state-machine, idempotency, concurrency, audit, or outbox rules.

---

# 5. Dual control / separation of duties

Configurable two-person approval is required for `FINANCIAL_CRITICAL` and selected `HIGH` risk operations, including:

- enabling live payments;
- enabling live refunds;
- enabling live payouts;
- enabling paid leads;
- enabling automatic assignment/confirmation;
- changing Stripe/payment credentials or payout provider credentials;
- changing vendor compensation formulas;
- changing payout destination/mapping rules;
- changing marketplace fee/commission rules;
- changing provider eligibility/trust rules that affect financial execution;
- changing retention rules for restricted data;
- replaying financial integration events;
- overriding reconciliation mismatches;
- enabling unrestricted external email/SMS/automation.

Required approval record:

```text
proposed_by
approved_by
approved_at
reason
configuration_hash
release_sha
environment
```

The proposer and approver must be different principals for dual-control actions.

---

# 6. Configuration governance

Production configuration is controlled state, not an informal `.env` edit.

Create or implement an equivalent immutable history model:

```text
configuration_versions
```

Record:

```text
config_key
old_value_hash
new_value_hash
environment
changed_by
approved_by
changed_at
release_sha
configuration_set_hash
```

Never put secret values in audit/history rows.

Govern at minimum:

- capability flags;
- provider endpoints;
- Keycloak issuer/audience/client configuration;
- Odoo mappings;
- Codestra/Kong/middleware endpoints;
- Klyrow/Telnexa/n8n routing;
- Stripe/payment/payout settings;
- provider matching/eligibility rules;
- upload limits;
- retention rules;
- rate limits;
- financial controls;
- export controls;
- notification policy.

Unauthorized production configuration drift is a launch blocker.

---

# 7. Secrets-management architecture

`.env` files are allowed for local development only where repository policy permits. Production requires a secret manager, Vault/KMS-backed mechanism, or an equivalent controlled secret store.

Inventory every production secret with:

```text
secret_id
owner
purpose
rotation_interval
last_rotated_at
next_rotation_at
environment
consumers
status
```

Separate credentials for:

- PostgreSQL;
- Redis where authentication is used;
- Keycloak/OIDC machine clients;
- Codestra/Kong/middleware;
- Odoo;
- Klyrow;
- Telnexa;
- n8n;
- object storage;
- malware scanning;
- geocoding;
- business-verification providers;
- payment/refund provider;
- payout provider;
- analytics/error-reporting providers.

Hard rules:

```text
No production secret in Git.
No production secret in a Docker image layer.
No production secret in logs, traces, audit or event payloads.
No production secret in frontend build variables.
No long-lived shared secret where scoped short-lived machine identity is available.
```

---

# 8. Event schema registry and compatibility

The existing Marketplace V2 event registry remains authoritative. Add machine-readable contracts under a stable location such as:

```text
apps/api/app/events/contracts/
```

Examples:

```text
project_request.submitted.v1.json
quote.accepted.v1.json
booking.confirmed.v1.json
job.completed.v1.json
payment.captured.v1.json       # only when payment capability is approved
payout.confirmed.v1.json       # only when payout capability is approved
```

CI must verify:

- schema validity;
- historical version immutability;
- breaking changes require a new major event version;
- registered consumers remain compatible;
- event payload classification permits every field;
- unknown events fail terminally instead of being marked delivered.

No Odoo, Codestra, n8n, Klyrow, Telnexa, or analytics consumer may depend on an undocumented event contract.

---

# 9. Provider certification matrix

Provider readiness is evidence-backed state, not a boolean assertion.

States:

```text
NOT_CONFIGURED
CONFIGURED
SANDBOX_TESTING
SANDBOX_CERTIFIED
PRODUCTION_CREDENTIALS_INSTALLED
PRODUCTION_VALIDATED
READY
SUSPENDED
```

Evidence should include, where applicable:

- authentication test;
- happy-path request;
- timeout behavior;
- `429` behavior;
- upstream `5xx` behavior;
- signature/authentication callback test;
- duplicate callback test;
- idempotency behavior;
- reconciliation behavior;
- data-classification review;
- last certification timestamp;
- source SHA/image digest/configuration hash used for certification.

A provider becomes `READY` only when all mandatory checks for that provider pass and evidence is not stale.

---

# 10. Circuit-breaker policy

Every external adapter that can materially degrade the platform must define:

```text
CLOSED
OPEN
HALF_OPEN
```

Trip conditions include configurable thresholds for:

- consecutive/rolling `5xx` errors;
- timeouts/network failures;
- authentication/configuration failures;
- rate-limit storms;
- repeated invalid response contracts.

Open behavior:

```text
provider unhealthy
→ stop hammering provider
→ mark dependent capability degraded/unavailable where required
→ create operational exception
→ alert
→ recover only through controlled half-open probes
```

Apply to Codestra/middleware, Odoo, Klyrow, Telnexa, n8n, geocoding, business verification, payments, payouts, storage/scanning, and any later external provider.

Circuit state in Redis is derived/disposable; authoritative incidents/exceptions belong in PostgreSQL.

---

# 11. Provider operation retry classification

Each adapter operation must declare one of:

```text
SAFE_TO_RETRY
IDEMPOTENT_WITH_KEY
RECONCILIATION_REQUIRED
NEVER_AUTOMATICALLY_RETRY
```

Examples:

```text
GET provider status
→ SAFE_TO_RETRY

POST transactional email/SMS
→ provider-specific; usually IDEMPOTENT_WITH_KEY where supported

POST payment capture/refund
→ IDEMPOTENT_WITH_KEY only when provider contract guarantees it; otherwise RECONCILIATION_REQUIRED

POST payout
→ NEVER_AUTOMATICALLY_RETRY unless provider idempotency semantics are contractually proven
```

Ambiguous provider outcomes must enter `RECONCILIATION_REQUIRED` instead of blindly retrying a real-world side effect.

---

# 12. Database/domain financial invariants

Financial and compensation correctness must not depend only on service code.

Use database constraints, partial unique indexes, immutable snapshots, and domain-policy tests where possible.

Minimum invariants when the related capability exists:

- one authoritative captured payment per provider/payment intent identity;
- no duplicate refund for the same approved refund command/idempotency identity;
- payout amount must be positive;
- earning/adjustment amounts must have explicit sign and reason semantics;
- compensation snapshot is immutable after the earning basis is committed;
- no payout for ineligible/unreleased earnings;
- no payout submission without required approval;
- no payout confirmation twice;
- no job-completion financial side effect before authoritative job completion;
- no paid-lead charge without an eligible lead/opportunity contract;
- currency is explicit and consistent;
- no floating-point money.

A failed financial invariant must reject the entire authoritative transaction.

---

# 13. Explicit audit immutability

`audit_events` is append-only.

Application identities must not have:

```text
UPDATE audit_events
DELETE audit_events
```

Admin APIs expose read/query/export under permission; they do not mutate historical audit events.

For stronger tamper evidence, support or plan hash chaining:

```text
previous_hash
event_hash
```

Audit metadata must include request/correlation identity, actor, tenant/legal entity/provider scope, reason where required, and safe before/after identifiers/hashes without copying secrets or excessive PII.

---

# 14. Append-only financial journal

When payments, marketplace fees, earnings, adjustments, refunds, or payouts become live, use an append-only journal instead of relying only on mutable current-state rows.

Conceptual table:

```text
financial_journal_entries
```

Entry types may include:

```text
PAYMENT_AUTHORIZED
PAYMENT_CAPTURED
PAYMENT_FAILED
REFUND_APPROVED
REFUND_SUBMITTED
REFUND_CONFIRMED
EARNING_ACCRUED
EARNING_ADJUSTMENT
EARNING_RELEASED
PAYOUT_APPROVED
PAYOUT_SUBMITTED
PAYOUT_CONFIRMED
PAYOUT_FAILED
PAYOUT_REVERSAL
FEE_ACCRUED
RECONCILIATION_ADJUSTMENT
```

Never edit an old journal entry. Corrections create compensating entries. Journal events must reconcile to provider statements and current aggregate projections.

---

# 15. Full data-retention matrix

Do not use one generic retention period.

Define retention individually for at least:

- customer profile;
- address/property;
- ProjectRequest;
- provider and worker profile;
- credentials/verification evidence;
- quote/conversation;
- booking/job;
- review/dispute;
- uploaded document/evidence;
- consent/preferences;
- payment/refund/payout records;
- earning/financial journal;
- audit;
- integration outbox/inbox payload;
- webhook payload;
- operational exception;
- analytics/projection data.

Each category declares:

```text
retention_class
retention_duration
legal_hold_behavior
deletion_or_anonymization_method
backup_expiration_behavior
projection_cleanup_behavior
```

Retention changes are controlled configuration and may require dual approval.

---

# 16. Data deletion/anonymization workflow

Privacy deletion is a governed domain workflow, not direct row deletion.

Commands should be equivalent to:

```text
RequestDataDeletion
ApproveDataDeletion
ExecuteDataDeletion
```

The workflow determines:

- what must be retained for legal, security, dispute, payment, or audit obligations;
- what may be anonymized;
- what must remain in the financial journal;
- what must be removed or anonymized in Odoo projections;
- what must be removed from object storage;
- what must be removed from analytics/search indexes;
- how deletion propagates to downstream processors;
- how backup expiration is handled.

Every deletion/anonymization run is auditable and retry-safe.

---

# 17. Strong document/upload controls

In addition to antivirus/malware scanning, enforce:

- extension allowlist by upload purpose;
- MIME sniffing;
- magic-byte validation;
- safe PDF/image parsing;
- archive-bomb protection;
- encrypted/password-protected file policy;
- maximum page count;
- maximum decompressed size;
- image-dimension/pixel limits;
- metadata sanitization where appropriate;
- filename normalization;
- private object ACLs;
- short-lived signed download URLs;
- tenant/record authorization on every download.

Example:

```text
filename says PDF
but magic bytes say executable
→ REJECTED
```

Only `CLEAN` objects may attach to authoritative business aggregates.

---

# 18. Browser/API CSRF, CORS and security-header policy

Explicitly define production:

- allowed origins;
- allowed methods;
- allowed headers;
- credential/cookie behavior;
- CSRF controls where cookie/BFF sessions are used;
- Content-Security-Policy;
- `frame-ancestors`/clickjacking policy;
- `Referrer-Policy`;
- `Permissions-Policy`;
- HSTS;
- secure cookie attributes;
- browser token/session storage decision.

Never ship production with:

```text
Access-Control-Allow-Origin: *
```

for authenticated/private APIs.

If browser bearer tokens are used instead of the preferred BFF/session model, that is an explicit security ADR with compensating controls.

---

# 19. Abuse controls

Protect the platform edge and sensitive workflows against:

- ProjectRequest/lead spam;
- credential stuffing;
- login/OTP abuse;
- provider-signup abuse;
- quote/message spam;
- document-upload abuse;
- webhook floods;
- API scraping;
- customer/provider enumeration;
- IDOR probing;
- admin/ops endpoint abuse;
- export abuse;
- replay/retry abuse.

Use layered controls:

```text
IP limits
identity limits
provider/tenant limits
route-specific limits
resource-specific limits
progressive throttling
proof/challenge where justified
```

Rate-limit state may be Redis-backed, but security events and enforced suspensions require durable audit/operational evidence.

---

# 20. PostgreSQL privilege separation

Never run the application as PostgreSQL superuser.

Define separate roles such as:

```text
breero_api
breero_worker
breero_migration
breero_readonly
breero_backup
```

Principle:

```text
API
→ only required CRUD/business-table privileges

Worker
→ only worker-required tables/operations

Migration
→ DDL/migration authority; not normal runtime identity

Readonly/operations
→ SELECT on approved views/tables only

Backup
→ minimum backup privileges
```

`audit_events` update/delete privileges must be denied to normal application roles.

---

# 21. Row-level security decision

The architecture must explicitly state one of:

```text
RLS = intentionally not used;
tenant isolation is enforced at application/query layer and continuously negative-tested
```

or:

```text
RLS = defense-in-depth on selected tenant-sensitive tables
```

Do not leave RLS undefined.

If selected RLS is used, session/transaction tenant context, migration behavior, worker identities, privileged support flows, and test coverage must be explicitly designed. RLS does not replace application authorization.

---

# 22. Data export controls

Define explicit permissions, for example:

```text
CRM_EXPORT
CUSTOMER_EXPORT
PROVIDER_EXPORT
MARKETPLACE_EXPORT
FINANCIAL_EXPORT
PII_EXPORT
AUDIT_EXPORT
```

A generic admin role must not automatically be allowed to bulk-dump all data.

Exports must be:

- authorized;
- purpose/reason bound where sensitive;
- audited;
- rate limited;
- classified;
- watermarked where appropriate;
- generated asynchronously for large datasets;
- encrypted at rest;
- delivered via short-lived access;
- automatically expired/deleted;
- prevented from containing classes not authorized for the requester.

---

# 23. Support impersonation policy

If BREERO implements “view as customer/provider,” silent impersonation is forbidden.

Require:

```text
SUPPORT_IMPERSONATE
reason
short TTL
visible UI banner
full audit
explicit target principal
```

While impersonating, prohibit or separately re-authorize:

- payment/refund/payout actions;
- credential verification;
- security configuration;
- high-risk PII export;
- provider bank/payout destination changes;
- break-glass actions.

Impersonation must never issue a reusable target user credential/token.

---

# 24. Environment promotion rules

Promotion flow:

```text
development
→ staging
→ production
```

The **same immutable artifact digest** is promoted. Only environment configuration/secrets differ.

Hard rule:

```text
Do not rebuild the application artifact between staging certification and production release.
```

Release identity includes source SHA, image digest, migration head, SBOM digest, provenance/signature, and approved configuration snapshot/hash.

---

# 25. Database migration compatibility matrix

Every migration PR declares:

```text
compatible_with_previous_api_image
compatible_with_next_api_image
requires_backfill
backfill_idempotent
requires_maintenance
safe_rollback
expected_lock_duration
large_table_impact
index_build_strategy
```

Use expand → compatible deploy → backfill → validate → contract.

Destructive contract migrations require proof that no active previous application version depends on the removed schema.

---

# 26. Feature/capability ownership

Every capability/feature flag must include metadata equivalent to:

```text
owner
risk_level
dependencies
approval_required
activation_environment
activated_by
activated_at
review_or_expiration_date
```

Risk levels:

```text
LOW
MEDIUM
HIGH
FINANCIAL_CRITICAL
```

Examples:

```text
payments
risk = FINANCIAL_CRITICAL
approval = dual control

payouts
risk = FINANCIAL_CRITICAL
approval = dual control

automatic_assignment
risk = HIGH
approval = operations + product

marketing
risk = HIGH
approval = legal/compliance + operations
```

Deployment does not imply activation.

---

# 27. On-call and incident-management runbooks

Create P0 runbooks for at least:

- PostgreSQL unavailable;
- Keycloak unavailable or issuer/JWKS failure;
- Codestra/Kong/middleware unavailable;
- Odoo unavailable;
- Klyrow unavailable;
- Telnexa unavailable;
- n8n unavailable;
- geocoding unavailable;
- object storage/scanner unavailable;
- Stripe/payment provider unavailable;
- payout provider unavailable;
- outbox stuck/backlogged;
- inbox stuck/backlogged;
- webhook signature attack/flood;
- payout/payment/reconciliation mismatch;
- malware upload;
- credential compromise;
- suspected cross-tenant exposure;
- database/object-storage exposure.

Every runbook defines:

```text
detection
severity
owner
immediate containment
customer/provider impact
safe degraded mode
recovery
verification
post-incident evidence
```

---

# 28. Explicit degraded-mode behavior

Every dependency must have defined fail-open/fail-closed behavior.

Examples:

```text
Odoo unavailable
→ marketplace transactions continue
→ CRM projections queue/retry
→ no authority shifts to Odoo

Klyrow unavailable
→ business transaction may complete if email is not required for correctness
→ notification intent remains queued

Telnexa unavailable
→ business transaction may complete if SMS is not required for correctness
→ delivery remains queued/suppressed per policy

Codestra/middleware unavailable
→ authoritative BREERO transaction commits
→ outbox queues eligible integration work
→ external side effect waits

n8n unavailable
→ approved automation pauses
→ no direct DB workaround

geocoder unavailable
→ new serviceability/address qualification that depends on geocoding fails closed or pauses
→ existing authoritative records remain safe

payment provider ambiguous result
→ payment enters reconciliation/uncertain state
→ no blind duplicate capture/refund

payout provider ambiguous result
→ payout enters reconciliation/uncertain state
→ no automatic resubmission unless idempotency is proven
```

Degraded behavior must be represented in user/ops state, not hidden behind fake success responses.

---

# 29. Capacity planning and load proof

Maintain baseline assumptions for:

```text
requests_per_second
concurrent_users
daily_project_requests
daily_quotes
daily_bookings
daily_jobs
daily_messages
daily_uploads
average_and_max_file_size
peak_webhooks_per_second
outbox_events_per_day
inbox_events_per_day
DB_growth_per_month
Redis_queue_peak
worker_concurrency
```

Load test at:

```text
normal expected load
2x expected peak
failure burst / retry storm
```

Capacity proof must include DB connection pools, worker saturation, queue age, rate limits, storage throughput, webhook ingestion, and graceful provider degradation.

---

# 30. Dependency, lockfile, image and SBOM policy

Require:

- Python dependency lock/fully reproducible pinning strategy;
- `pnpm-lock.yaml` with frozen install;
- pinned container base images, preferably by digest for release;
- no `latest`-based production identity;
- dependency update process;
- critical/high vulnerability SLA;
- SBOM per release image;
- provenance/signature verification;
- license/policy checks where required.

Production builds must not unexpectedly resolve “latest compatible” dependency versions at build time.

---

# 31. Readiness evidence expiration

Passing evidence is valid only for the release/configuration it proves and for a bounded time.

Recommended defaults unless a stricter control applies:

```text
OIDC/Keycloak E2E
→ valid 7 days and only for compatible issuer/client/configuration

backup/restore rehearsal
→ valid 30 days and must prove current migration family

provider certification
→ valid 90 days or until credential/config/API contract change, whichever occurs first

security test suite
→ must match current source SHA

staging canary
→ must match exact release image digest and approved config snapshot

migration rehearsal
→ must match candidate migration head
```

The readiness engine rejects missing, stale, mismatched, blocked, or failed evidence.

---

# 32. Human launch-approval record

Human production approval is a durable record, not a comment in chat or PR text.

Create or implement an equivalent model:

```text
launch_approvals
```

Fields:

```text
release_sha
image_digest
migration_head
environment
configuration_snapshot_hash
evidence_snapshot_hash
approved_by
approved_at
decision
comments
```

`READY` may be declared only when approval exists for the exact immutable release candidate and exact approved configuration snapshot.

A new source SHA, image digest, migration head, security-relevant configuration, or required evidence invalidates the prior approval as defined by policy.

---

# Financial-critical PR decomposition

Do not bundle all financial lifecycle implementation into one large PR. When financial capabilities are authorized for implementation, split into independently reviewable workstreams:

```text
FIN-1  payments + provider intents + webhook authority
FIN-2  refunds/disputes + reconciliation
FIN-3  provider compensation/earnings + immutable snapshots
FIN-4  payouts + dual control + payout provider integration
FIN-5  financial journal + statement reconciliation + closeout reporting
```

Each PR includes:

```text
implementation
additive migration where required
rollback/compatibility plan
unit tests
PostgreSQL integration tests
security/authorization tests
idempotency/concurrency tests
provider failure tests
OpenAPI/event contract changes
operational documentation
readiness evidence
```

No financial capability is activated merely because its implementation PR is CI-green or merged.

---

# Binding completion rule

A hardening control is not complete because documentation exists. Completion requires implementation plus current evidence proving the exact release candidate.

The following are not equivalent:

```text
DOCUMENTED
IMPLEMENTED
TESTED
CERTIFIED
ACTIVATED
```

Marketplace V2 remains `NO_GO` until the controlling production-readiness gates and all required P0 evidence pass. Capability activation remains a separate human-controlled action after deployment.