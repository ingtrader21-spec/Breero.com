# BREERO Ultimate Master Execution Map

Status: **binding branch and acceptance authority**

Source authority: `BREERO ULTIMATE MASTER FEATURES + SOFTWARE INSTALLATION + INFRASTRUCTURE MISSION` supplied on 2026-08-27.

This map applies that mission to the current repository. It does not replace supported technology, mark unimplemented domains complete, or activate protected production behavior.

Detailed API/forms/integration/release authority:

```text
docs/codex/BREERO_FEATURE_API_FORMS_DOCKER_MISSION.md
```

## 1. Required marketplace outcome

```text
PUBLIC WEBSITE
CUSTOMER MARKETPLACE
BOOKING AND QUOTE ENGINE
CLIENT ACCOUNTS
SERVICE PROVIDER NETWORK
PROVIDER CAPACITY
PROVIDER MATCHING
MANUAL DISPATCH
ADMINISTRATION
TRUST AND COMPLIANCE
REVIEWS
LEAD MANAGEMENT
COMMUNICATION
ANALYTICS
SECURITY
OBSERVABILITY
DEPLOYMENT
```

Landing pages, forms, dashboards, mock APIs and demo authentication are not a completed marketplace.

## 2. Existing architecture preserved

```text
BACKEND=FastAPI + Python 3.12
ORM=SQLAlchemy async
MIGRATIONS=Alembic
DATABASE=PostgreSQL 17 + PostGIS
CACHE_QUEUE=Redis + Celery
FRONTEND=Next.js 15 + React 19 + TypeScript
PACKAGE_MANAGER=pnpm + Turborepo
IDENTITY=Keycloak/OIDC
CONTAINERS=Docker + Docker Compose
EDGE=Caddy/Kong boundaries
CI=GitHub Actions
TESTS=pytest + Vitest + Testing Library + Playwright
```

The uploaded mission explicitly requires extending a supported existing architecture.

```text
ASP.NET_CORE_REWRITE=NOT_APPLICABLE
ENTITY_FRAMEWORK_REWRITE=NOT_APPLICABLE
AZURE_ONLY_REWRITE=NOT_APPLICABLE
FASTAPI_NEXT_POSTGRES_ARCHITECTURE=PRESERVED
```

Azure/Bicep may remain an optional future infrastructure choice, not a prerequisite rewrite.

## 3. Runtime and package policy

Before adding or changing software:

```text
classify REQUIRED | OPTIONAL | FUTURE | ALREADY_INSTALLED | NOT_APPLICABLE
check the repository for an equivalent
verify framework/runtime compatibility
review security, support, license and maintenance
prefer native framework capability
update lockfiles and environment examples
run the complete exact-head gate
```

Node 24 certification belongs in `chore/node24-runtime-certification`, not a feature branch.

## 4. Protected production posture and current enforcement status

Target protected values:

```text
AUTO_ASSIGN_PROVIDER=false
AUTO_CONFIRM_BOOKING=false
PAYMENTS_ENABLED=false
LIVE_PROVIDER_DISPATCH=false
LIVE_EMAIL_DELIVERY=false
LIVE_SMS_DELIVERY=false
LIVE_CALLBACKS=false
ODOO_DELIVERY_ENABLED=false
ODOO_WRITE_ENABLED=false
PROVIDER_ASSIGNMENT_MODE=MANUAL
MESSAGING_ENABLED=false
REVIEWS_ENABLED=false
FEATURED_PROVIDERS_ENABLED=false
LEAD_BILLING_ENABLED=false
```

A documented value is not an enforced kill switch.

Current planning blocker:

```text
LIVE_EMAIL_DELIVERY_POLICY=NOT_YET_PROVEN_IN_RUNTIME
LIVE_SMS_DELIVERY_POLICY=NOT_YET_PROVEN_IN_RUNTIME
```

Before a production release may assert zero email/SMS delivery, the respective adapter branch must add recognized fail-closed settings, enforce them in the worker/adapter even when a delivery URL or credential exists, park disabled events without provider calls or false delivery, expose the effective capability snapshot, and prove provider-call count zero in tests.

Until then:

```text
EMAIL_ZERO_SEND_GATE=FAIL
SMS_ZERO_SEND_GATE=FAIL
REQUEST_ONLY_PRODUCTION_RELEASE=NO_GO
```

## 5. Dependency-ordered branch program

Every heavy branch opens as a draft PR, owns one responsibility, preserves compatibility, reports exact SHAs and cannot deploy merely because CI is green.

### Phase A — governance, design, runtime, API and identity

```text
ci/required-check-governance
fe/enterprise-design-governance
chore/node24-runtime-certification
be/marketplace-v2-p0-api-foundation
be/api-contract-cleanup
be/auth-identity-tenancy-rbac
```

Acceptance includes one required `quality` aggregator, shared enterprise/marketplace UI authority, stable error/trace/pagination/OpenAPI contracts, immutable external identity binding, deny-by-default tenant/permission/record policy and local production-auth shutdown.

### Phase B — catalog, address, geography, timezone and hours

Branch:

```text
be/catalog-geography-timezone-hours
```

Owns categories, subcategories, services, slugs, descriptions, duration, buffers, pricing modes, required skills/licenses/compliance, address-provider abstraction, normalization, ZIP/ZIP+4, city/state/county, coordinates, IANA timezone, DST, BREERO service zones, hours, Sunday emergency and PostGIS queries/indexes.

Address-provider outage policy:

```text
REQUEST_ONLY_INTAKE=ACCEPT_FOR_MANUAL_REVIEW
COVERAGE_OR_SERVICEABILITY=NOT_ESTABLISHED
AUTOMATIC_AVAILABILITY_BOOKING_ASSIGNMENT=DENY
```

Tests cover spring/fall DST, ambiguous/non-existent time, Arizona, Hawaii, unsupported ZIP, provider outage and PostGIS coverage.

### Phase C — provider organizations, teams and workers

Branch:

```text
be/provider-network-teams
```

Owns applications, organizations, administrators, memberships, professionals/workers, services, skills, status and tenancy. Registration never equals approval.

### Phase D — provider coverage and schedule

Branch:

```text
be/provider-coverage-schedule
```

Owns ZIP/city/county/zone/radius coverage, weekly availability, exceptions, vacation, sick time, training, manual blocks, holidays, emergency schedule and overrides. Provider coverage cannot exceed BREERO's outer service boundary; availability cannot exceed BREERO hours.

### Phase E — canonical private document service

Branch:

```text
be/documents-private-storage
```

This is the single owner of object metadata, upload sessions, private storage, signed short-lived access, type/size/checksum validation, malware scanning, quarantine, cleanup, retention/deletion and object authorization.

No other branch may create a parallel upload/storage/quarantine pipeline.

### Phase F — provider compliance

Branch:

```text
be/provider-compliance
```

Owns identity, business, license, insurance, background and service-qualification requirements/status; expiration; reviewer decision; suspension; eligibility exclusion; compliance notes/history; and links to the canonical document service.

### Phase G — capacity, travel and atomic holds

Branch:

```text
be/scheduling-capacity-holds
```

Owns service duration, buffers, travel-estimation abstraction, booking consumption, holds, blocks, time off, daily job/work-minute limits, concurrent limits, emergency reserves, job/time capacity and 30-minute `HELD/CONVERTED/EXPIRED/RELEASED` lifecycle.

Mandatory race proof:

```text
Customer A and Customer B request the same final capacity simultaneously.
Only allowed capacity survives.
```

### Phase H — request, quote, booking and change-order lifecycles

```text
be/request-quote-lifecycle
be/booking-reschedule-cancel
be/change-orders
```

Preserve `INSTANT_BOOKABLE`, `QUOTE_REQUIRED`, and `REQUEST_ONLY`; versioned quotes/line items; customer decisions; booking/hold conversion; service-address timezone; cancellation/rescheduling; immutable history; idempotency/concurrency; and customer-approved change orders. No silent scope or payment mutation.

### Phase I — matching, scoring and manual dispatch

```text
be/provider-matching-scoring
be/manual-dispatch-assignment
fe/dispatch-console
```

Eligibility precedes scoring:

```text
active and approved provider/professional
valid compliance
service/skill qualified
coverage, schedule and capacity matched
no time-off/conflict
Sunday/emergency eligible
```

Configurable internal inputs may include availability, distance, exact skill, remaining capacity, reliability, eligible rating and acceptance history. Internal scores are not public.

```text
PROVIDER_ASSIGNMENT_MODE=MANUAL
AUTO_ASSIGN_PROVIDER=false
```

Recommendations may assist dispatch but do not assign automatically.

### Phase J — customer, provider, worker and internal portals

```text
fe/customer-marketplace-portal
fe/provider-organization-portal
fe/worker-field-service-portal
fe/operations-support-trust-portals
fe/admin-platform-portal
```

Portals use real APIs, authorization, persistence and the shared enterprise/marketplace UI. They do not fabricate KPIs, providers, queues, payments, reviews, messages or success data.

### Phase K — messaging, notifications and support

```text
be/messaging-conversations
be/notifications-templates
be/support-cases
fe/messaging-support-experience
```

Messaging requires authorized relationships and privacy-controlled disclosure. Notifications use versioned event/channel/language templates and durable delivery. Support keeps customer/provider messages distinct from private internal notes.

Email/SMS transport remains in separate adapter branches and disabled until runtime enforcement and activation gates pass.

### Phase L — reviews and provider performance

```text
be/reviews-moderation
be/provider-performance
fe/reviews-trust-experience
```

Only customers with eligible completed service create verified-job reviews. Support provider response, moderation, reporting and publication state. Internal risk scoring remains private.

### Phase M — leads and sponsored placement

```text
be/lead-management
be/featured-provider-infrastructure
fe/leads-commercial-admin
```

Lead and booking concepts remain distinct. Sponsored placement never overrides safety, qualification, coverage, license, compliance, schedule or capacity eligibility.

### Phase M.1 — shared durable delivery foundation

Complete `integration/outbox-inbox-webhooks` after identity and authorization, before finance. This branch owns the common transactional outbox, durable inbox, deduplication, retry, dead-letter and replay acceptance evidence. Phase P adds provider-specific adapters on this accepted foundation.

### Phase N — disabled finance infrastructure

```text
be/payments-refunds-infrastructure
be/provider-earnings-payouts
fe/finance-payment-experience
```

Do not begin before identity, authorization, audit, idempotency, concurrency, quote/booking, durable delivery, reconciliation and finance separation-of-duty foundations pass.

```text
PAYMENTS_ENABLED=false
PAYOUTS_ENABLED=false
```

### Phase O — analytics, privacy, retention and observability

```text
be/analytics-observability
be/privacy-retention-exports
fe/analytics-system-health
```

Own structured logs/traces/metrics/health, queue/lease age, marketplace KPIs, PII redaction/classification, retention, audited asynchronous exports, dashboards and runbooks.

### Phase P — durable integrations and separate adapters

Common reliability:

```text
integration/provider-adapter-reconciliation
```

Provider-specific branches:

```text
integration/kong-codestra-gateway
integration/odoo-projection
integration/n8n-orchestration
integration/klyrow-email
integration/telnexa-sms
```

Each provider has separate credentials, tests, review, activation, degraded behavior and rollback. Odoo is a projection/workspace; n8n orchestrates but does not own correctness.

### Phase Q — development, CI, staging and production

```text
chore/local-development-bootstrap
ci/security-performance-matrix
ci/docker-release-platform
infra/production-topology
release/isolated-staging-certification
release/production-candidate
```

Own reproducible setup, safe demo data/adapters, full test matrix, performance smoke, immutable images, SBOM/provenance, one canonical private production topology, backup/restore, staging UAT, rollback rehearsal, canary and abort thresholds.

Production is never the first migration target. A migration one-shot must pass and the expected head must be verified before new services or public routing.

## 6. Design acceptance

Binding authorities:

```text
docs/design-system.md
docs/marketplace-experience-system.md
docs/design-system-migration.md
```

Every applicable changed surface handles search/filter/sort/pagination, forms, drawers/dialogs, loading, empty, error, restricted, disabled, success, 320–1440+ responsive behavior, keyboard/screen reader/reduced motion and Chromium/Firefox/WebKit. Request, quote, booking, assignment, job and completion remain distinct.

## 7. API acceptance

Every operation documents owner, audience, auth, permission, tenant/legal entity, ownership/record policy, resource state, capability, idempotency, concurrency, request/response, errors/headers, rate limit, event and deprecation.

An endpoint is not complete merely because it exists. Authorization, persistence, concurrency, migrations and failure behavior must be tested.

## 8. Complete test matrix

```text
unit
integration
PostgreSQL/PostGIS
API contract
authentication/authorization/ownership/tenancy
booking/quote state
ZIP/zone/timezone/DST/hours/emergency
matching/capacity/holds/double-booking
cancellation/rescheduling/assignment/reassignment
compliance/private files
reviews/moderation
rate limiting/abuse
accessibility/responsive/E2E
migration/rollback
security/performance
backup/restore
```

## 9. Final completion rule

Nothing is complete merely because it renders or an endpoint exists.

Completion requires tested authorization, persistence, concurrency, migrations, rollback/forward-fix, exact-head CI, final-SHA review, staging evidence for releases and enforced protected capabilities.

## 10. Historical authority snapshot — 2026-08-27

```text
HISTORICAL_MAIN_SHA=35beb55eedb3f58eb39caf40ffaa9795978d6ee7
DESIGN_AUTHORITY_PR=67
DASHBOARD_INTERACTIONS_PR=69
IDENTITY_RBAC_PR=68
PLANNING_AUTHORITY_PR=47
PRODUCTION_DEPLOYED=NO
LIVE_SERVER_CHANGED=NO
ULTIMATE_MISSION_COMPLETE=NO
```

This snapshot records the original planning baseline. Resolve current implementation and remaining work from `docs/architecture/CURRENT_SYSTEM.md`, accepted `main` code, and current PR state. It does not override subsequently accepted identity, onboarding, or booking-intent implementations.
