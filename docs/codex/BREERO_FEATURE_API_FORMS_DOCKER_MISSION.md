# BREERO Feature, API, Forms, CTA, and Docker Production Mission

Status: **binding implementation and release authority**

Companion authority:

```text
docs/codex/BREERO_ULTIMATE_MASTER_EXECUTION_MAP.md
docs/product/BREERO_ANGI_COMPETITIVE_PRODUCT_CONTRACT.md
docs/design-system.md
docs/marketplace-experience-system.md
```

This mission improves the existing BREERO monorepo. It does not authorize a rewrite, an unrelated repository, a direct push to protected `main`, an unsafe mega-branch, early capability activation, or production deployment without the gates below.

## 1. Existing architecture

Extend the supported repository architecture:

```text
BACKEND=FastAPI + Python 3.12 + SQLAlchemy + Alembic
DATABASE=PostgreSQL 17 + PostGIS
CACHE_QUEUE=Redis + Celery
FRONTEND=Next.js 15 + React 19 + TypeScript
WORKSPACE=pnpm + Turborepo
IDENTITY=Keycloak/OIDC
CONTAINERS=Docker + Docker Compose
EDGE=Caddy/Kong boundaries
CI=GitHub Actions
TESTS=pytest + Vitest + Testing Library + Playwright
```

Do not replace working technology merely because another stack is mentioned in a target specification.

## 2. Non-negotiable branch policy

Every heavy feature receives its own branch and draft PR from the latest human-merged `main`, except an explicitly temporary stacked review branch that is synchronized before merge.

```text
ci/required-check-governance
fe/enterprise-design-governance
chore/node24-runtime-certification
be/marketplace-v2-p0-api-foundation
be/api-contract-cleanup
be/auth-identity-tenancy-rbac
be/public-submissions-hardening
fe/public-forms-cta-hardening
integration/outbox-inbox-webhooks
be/documents-private-storage
be/provider-network-teams
be/provider-coverage-schedule
be/provider-compliance
be/catalog-geography-timezone-hours
be/scheduling-capacity-holds
be/request-quote-lifecycle
be/booking-reschedule-cancel
be/change-orders
be/provider-matching-scoring
be/manual-dispatch-assignment
fe/dispatch-console
fe/customer-marketplace-portal
fe/provider-organization-portal
fe/worker-field-service-portal
fe/operations-support-trust-portals
fe/admin-platform-portal
integration/kong-codestra-gateway
integration/odoo-projection
integration/n8n-orchestration
integration/klyrow-email
integration/telnexa-sms
ci/docker-release-platform
infra/production-topology
release/isolated-staging-certification
release/production-candidate
```

Financial work remains later and separate:

```text
be/payments-refunds-infrastructure
be/provider-earnings-payouts
fe/finance-payment-experience
```

Each branch must have one primary responsibility, preserve accepted compatibility, regenerate contracts when needed, prove applicable authorization/idempotency/concurrency/failure behavior, identify affected capabilities, report exact SHAs and CI, and never deploy merely because CI is green.

## 3. API contract cleanup

Create one authoritative API registry for every route:

```text
method and path
owner
audience
authentication
permission
capability
tenant/legal-entity scope
ownership and record policy
resource state
Idempotency-Key/request hash
If-Match/version
request/response schema
error and header contract
rate limit
emitted event
deprecation state
```

State-changing commands require the applicable authentication, permission, tenant, record policy, capability, idempotency, version, state transition, audit and transactional-outbox checks.

Preserve:

```text
X-Request-ID
X-Correlation-ID
WWW-Authenticate
Retry-After
Allow
ETag
```

Routers do not own business rules and do not call external providers inside the authoritative PostgreSQL transaction.

## 4. Public and account API readiness

Current compatible public APIs remain documented and tested:

```http
GET  /api/v1/public/capabilities
GET  /api/v1/services
GET  /api/v1/services/{service_id}
GET  /api/v1/services/{service_id}/questions
POST /api/v1/service-requests
POST /api/v1/contact
POST /api/v1/provider-interest
POST /api/v1/privacy-requests
POST /api/v1/communications/preferences
```

Current account APIs remain compatible while local production authentication is disabled under OIDC policy.

Target provider, worker, operations, admin, messaging, review, payment and payout routes remain absent or capability-denied until their owning branch is accepted.

## 5. Public-submission API hardening

Branch:

```text
be/public-submissions-hardening
```

Implement:

- typed service-request, contact, provider-interest, privacy and communication-preference commands;
- server-side consent and versioned disclosure evidence;
- catalog/state validation;
- normalized contact data with approved original-value handling;
- stable idempotency and unique-constraint race handling;
- same key/same body replay and changed-body conflict;
- atomic submission, audit and outbox commit;
- visible `Retry-After` rate limiting;
- intentional Redis failure behavior;
- abuse controls and PII redaction;
- pending-configuration, pending-delivery, delivered, retryable and terminal states;
- dispatcher ownership and SLA fields;
- no appointment, provider assignment, payment or confirmation from intake.

Mandatory tests include honeypot, consent, catalog/state rejection, replay/conflict, concurrent duplicate, rate limiting, disabled middleware, downstream outage and PII-redaction behavior.

## 6. Address-provider outage policy

Address validation is an optional provider dependency for the accepted request-only intake, but it is mandatory before any automatic serviceability, availability, slot, capacity, booking or assignment decision.

When the address/geocoding provider is disabled, unavailable, times out, or returns an ambiguous result:

```text
REQUEST_ONLY_INTAKE=ACCEPT_FOR_MANUAL_REVIEW
ADDRESS_STATUS=UNVERIFIED_OR_PENDING_REVIEW
COVERAGE_STATUS=NOT_ESTABLISHED
AUTOMATIC_SERVICEABILITY=DENY
AVAILABILITY_OR_SLOT_PROMISE=DENY
BOOKING_CONFIRMATION=DENY
PROVIDER_ASSIGNMENT=DENY
```

The customer may submit the request with clear manual-review language. The system must not reject all intake merely because automatic address verification is unavailable, and it must not imply that BREERO coverage has been established.

Tests must prove request preservation, no automatic serviceability decision, no slot/booking/assignment creation, operator visibility, retry/reconciliation and customer-facing status.

## 7. Forms and CTA hardening

Branch:

```text
fe/public-forms-cta-hardening
```

Use reusable tested form boundaries and one shared submission client/error/idempotency layer.

Required behavior:

- stable idempotency key for an unchanged retry;
- new key only after material payload change;
- preserve key after ambiguous network/503 failure;
- preserve entered data after recoverable failure;
- backend-safe field errors and correlation reference;
- `Retry-After` guidance;
- double-submit prevention;
- focus first invalid field and accessible error/status semantics;
- live catalog data;
- the address-provider outage policy above;
- no false provider, price, appointment, booking or payment confirmation;
- 320px through large-desktop support.

Global request-first CTA language:

```text
Book a service -> Request service
Check availability -> Request service options
```

One CTA registry owns ID, label, href, analytics event, page family, capability and fallback. CI rejects dead routes, placeholder anchors, duplicate analytics IDs, actionless buttons, disabled-capability actions and misleading book/pay/confirm copy.

## 8. Common integration reliability

Branch:

```text
integration/outbox-inbox-webhooks
```

Own only provider-neutral reliability:

- transactional outbox;
- durable authenticated inbox;
- claim-token-safe leases and stale recovery;
- event uniqueness, timestamp and replay validation;
- retry/backoff/terminal states;
- authorized manual retry/replay;
- operational exceptions;
- reconciliation and crash tests;
- common adapter interface, redaction and correlation contracts.

No provider credential, transport activation or vendor-specific business mapping belongs in this branch.

## 9. Provider-specific integrations

Each adapter has a separate branch, credentials, approval, health model, tests, rollback boundary and activation change:

```text
integration/kong-codestra-gateway
integration/odoo-projection
integration/n8n-orchestration
integration/klyrow-email
integration/telnexa-sms
```

Boundaries:

- BREERO PostgreSQL/PostGIS is authoritative marketplace state;
- Kong/Codestra owns transport and control policy, not marketplace truth;
- Odoo 19 is a CRM projection/workspace and preserves the accepted `breero_crm`/`breero.sync.event` compatibility plan;
- n8n executes allowlisted orchestration and never writes BREERO tables directly;
- Klyrow transports approved email only;
- Telnexa transports approved SMS only;
- each adapter proves authentication, timeout, idempotency, retries, degraded behavior, reconciliation, redaction and disabled-mode behavior.

A failure or certification blocker in one adapter must not couple or block unrelated adapters.

## 10. Live email and SMS enforcement

Documentation flags are not safety controls by themselves. Before any request-only production release can claim `EMAIL_SENDS=0` or `SMS_SENDS=0`, the relevant adapter branch must implement and test authoritative runtime settings:

```text
LIVE_EMAIL_DELIVERY=false
LIVE_SMS_DELIVERY=false
```

Required enforcement:

- settings are recognized fields with fail-closed production defaults;
- adapter and worker check the setting even when a delivery URL/credential exists;
- disabled events park without a provider call or false delivered result;
- startup/readiness does not require a disabled optional provider;
- tests assert provider-call count zero when disabled;
- deployment capability snapshot records the effective value;
- activation occurs only in a separate protected change.

Until this code exists and exact-head tests pass:

```text
EMAIL_ZERO_SEND_GATE=NOT_PROVEN
SMS_ZERO_SEND_GATE=NOT_PROVEN
PRODUCTION_REQUEST_ONLY_RELEASE=NO_GO
```

## 11. Canonical private-document ownership

Branch:

```text
be/documents-private-storage
```

This is the single owner of object metadata, upload sessions, private storage, signed short-lived access, type/size/checksum validation, malware scanning, quarantine, cleanup, retention/deletion and object authorization.

Provider compliance owns document requirements, verification state, reviewer decisions, expiration and provider eligibility, but consumes the canonical document service instead of creating a second storage pipeline.

## 12. Portal design and interactions

Portal branches use the binding enterprise/marketplace design system and real typed APIs only.

Every changed surface must deliberately handle:

```text
loading
empty
error
restricted
disabled
success
search/filter/sort/pagination where applicable
forms and backend validation
drawers/dialogs and focus recovery
mobile
keyboard
screen-reader semantics
reduced motion
Chromium/Firefox/WebKit
```

No fabricated KPI, queue, provider, booking, rating, review, message, payment or success data.

## 13. Docker release platform

Branch:

```text
ci/docker-release-platform
```

Select one canonical production Compose authority. The topology includes frontend, API, one-shot migration, worker, scheduler, PostgreSQL/PostGIS, Redis, external Caddy edge and internal private network.

Require immutable digests, no public data-plane ports, non-root/read-only containers, dropped capabilities, resource/PID limits, health/heartbeat, secret references, Compose validation, HIGH/CRITICAL scans, SBOM, provenance, release manifest and rollback images.

Deployable frontend identity uses only:

```text
NEXT_PUBLIC_KEYCLOAK_ISSUER=https://auth.codestra.co/realms/codestra
```

## 14. Isolated staging certification

Branch:

```text
release/isolated-staging-certification
```

Deploy the exact candidate digests with isolated PostGIS, Redis, API, worker, scheduler, frontend, DNS/TLS, secrets and synthetic personas.

Prove clean/supported migrations, OpenAPI/client compatibility, OIDC, forms/CTAs, request-only behavior, manual scheduling/confirmation, disabled protected capabilities, idempotency/concurrency, crash/lease recovery, adapter-disabled behavior, browser/accessibility/responsive matrix, backup/restore and rollback rehearsal.

Production is `NO_GO` when staging cannot be proven.

## 15. Production migration and routing gate

Branch:

```text
release/production-candidate
```

A release containing an Alembic migration must execute this exact ordering before any new API, worker, scheduler or public route receives traffic:

```text
1. verify approved release SHA, image/config digests and expected migration head
2. verify current database head and supported upgrade path
3. create dated database/object/config backup
4. restore the backup into an isolated target and pass integrity/application smoke
5. place the application in the approved migration-compatible traffic state
6. run the digest-pinned one-shot migration job
7. require migration exit status 0
8. verify alembic current == expected release head and alembic heads is singular/expected
9. run schema/application smoke against the migrated database
10. start or promote the new API, worker and scheduler digests
11. require readiness and worker/scheduler health
12. canary privately
13. route public traffic only after every preceding gate passes
```

Abort before routing on migration failure, unexpected head, schema drift, data-integrity uncertainty, failed smoke, failed readiness or unavailable rollback/forward-fix authority.

Do not start new code against an old schema. Do not blindly downgrade a migration that is not proven reversible; use the reviewed restore or forward-fix decision tree.

## 16. Production preflight and zero-activity evidence

Before deployment revalidate current host capacity, listeners, DNS/TLS, Caddy, networks, volumes, database head, backup/restore, monitoring and rollback artifacts. Use a protected production environment and exact staging-certified digests.

Required request-only evidence remains:

```text
PAYMENTS_ATTEMPTED=0
PAYOUTS_ATTEMPTED=0
PAID_LEAD_CHARGES=0
AUTOMATIC_ASSIGNMENTS=0
AUTOMATIC_CONFIRMATIONS=0
EMAIL_SENDS=0
SMS_SENDS=0
ODOO_WRITES=0
N8N_EXECUTIONS=0
MIDDLEWARE_DELIVERIES=0
```

A zero-send assertion is valid only when the corresponding runtime kill switch is implemented and tested as described above.

## 17. Codex operating instructions

Codex must inspect current GitHub state, stop at unmerged prerequisites, create only the next permitted branch, implement code/tests/migrations/contracts/docs together, open/update a draft PR, never self-approve or bypass protection, never weaken tests, never activate through route/schema/UI presence, never use production as staging, and return exact SHAs, commits, files, tests, runs, review state, blockers and next branch.

## 18. Status vocabulary

```text
CODE_READY=YES|NO
REVIEW_READY=YES|NO
MERGE_READY=YES|NO
STAGING_READY=YES|NO
PRODUCTION_READY=YES|NO
PRODUCTION_DEPLOYED=YES|NO
CAPABILITY_ACTIVE=YES|NO
```

These statuses are not interchangeable.