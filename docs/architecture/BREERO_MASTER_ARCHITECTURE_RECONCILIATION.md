# BREERO master architecture reconciliation

## Authority

The two new implementation specifications supplied on 2026-08-27 are the target implementation authority for BREERO feature, API, URL, domain-logic, portal, security, concurrency, observability and release work:

- `BREERO MASTER FEATURE ARCHITECTURE + API ENDPOINT + URL DESIGN`
- `BREERO COMPLETE LOGIC & SYSTEM ARCHITECTURE DESIGN`
- `docs/contracts/breero-master-contract.json`

They extend the current FastAPI, async SQLAlchemy, PostgreSQL/PostGIS, Alembic, Redis/Celery and Next.js architecture. They do not authorize a technology rewrite, a destructive route rename, a production deployment, or activation of protected side effects.

Source integrity:

```text
FEATURE_API_URL_SOURCE_LINES=3718
FEATURE_API_URL_SOURCE_SHA256=ee788511ec041d91c3587adf2e76b145b6bce828897ec2f69eed8b5db27fed7c
LOGIC_SYSTEM_SOURCE_LINES=4296
LOGIC_SYSTEM_SOURCE_SHA256=91626db8b18782aa7e12b551dd5ee8059404d7e20539399f2cccc51eac84290d
```

## Reconciliation rules

1. Preserve passing behavior and the complete accepted migration lineage.
2. Implement in dependency order, not page order.
3. Keep heavy responsibilities in separate branches and pull requests.
4. Do not call a route implemented merely because it is declared in the contract.
5. Existing public contracts remain available until a reviewed compatibility plan proves a safe replacement.
6. PostgreSQL is authoritative for bookings, holds, capacity, assignment, authorization and state.
7. Redis may support caching, rate limiting and Celery, but it is not the sole correctness boundary.
8. Business workflows live in application/domain services; routers remain HTTP adapters.
9. A provider must be eligible before scoring. Commercial placement may never override eligibility or compliance.
10. Customer-facing availability never exposes internal provider/professional identity, scores, addresses or private capacity.
11. Capacity changes, holds, booking submission, assignment, reassignment, cancellation and rescheduling use database transactions and concurrency controls.
12. Email, SMS, callbacks, Odoo writes, payments, automatic confirmation and automatic assignment remain disabled until their owning release gates explicitly pass.

## System entry contract

```text
breero.com
├── public website
├── /account/* client portal
├── /provider/* provider portal
├── /admin/* administration and dispatch
└── /api/v1/* FastAPI
```

Prefer same-origin `/api/v1` where practical. A separately deployed API may use `https://api.breero.com/api/v1`, but this does not change authentication, CSRF, CORS or authorization requirements.

## Domain ownership

```text
identity
clients
providers
compliance
catalog
addresses
geography
service_zones
timezones
scheduling
availability
capacity
bookings
matching
assignments
dispatch
messaging
notifications
reviews
leads
advertising
support
analytics
audit
feature_flags
observability
```

Each domain owns models, schemas, repository queries, application/domain services, permissions, events and typed exceptions. FastAPI routes do not own multi-step business transactions.

## Historical implementation snapshot — 2026-08-27

```text
MAIN=35beb55eedb3f58eb39caf40ffaa9795978d6ee7

IDENTITY_RBAC_PR=68
IDENTITY_RBAC_BRANCH=be/auth-identity-tenancy-rbac
IDENTITY_RBAC_HEAD=2f19401b9c6a0da18a14b6779767595f6e0903fc
IDENTITY_RBAC_REQUIRED_QUALITY_RUN=33118336443
IDENTITY_RBAC_REQUIRED_QUALITY=PASS

PROVIDER_ONBOARDING_PR=85
PROVIDER_ONBOARDING_BRANCH=be/provider-onboarding-api-completion
PROVIDER_ONBOARDING_HEAD=99cd22e1ce074f526746208ec3266aa4b750a4ed
PROVIDER_ONBOARDING_REQUIRED_QUALITY_RUN=33118650604
PROVIDER_ONBOARDING_REQUIRED_QUALITY=PASS

PRODUCTION_DEPLOYED=NO
LIVE_SERVER_CHANGED=NO
```

PR #68 owns identity, sessions, effective permission checks, tenant scope, portal context and protected internal-user provisioning. PR #85 is stacked on it and owns provider registration, provider profile, onboarding persistence, submission and administrator application decisions.

At that historical snapshot neither branch was merged. Both identity and provider onboarding have since reached the accepted baseline. Use `docs/architecture/CURRENT_SYSTEM.md`, current `main` source, and live PR state for implementation decisions; these historical check results do not establish current readiness.

## Compatibility decisions

### Client route family

The target contract uses `/api/v1/client/*`. The accepted code currently exposes several customer-owned resources under `/api/v1/customer/*`.

Implementation must add reviewed `/client/*` contracts or aliases before removing any existing `/customer/*` route. A destructive rename is not authorized by these documents.

### Booking intent versus booking

The target architecture explicitly separates pre-submission `booking_intents` from durable submitted `bookings`.

The accepted code already has the dedicated `BookingIntent` aggregate in `apps/api/app/domains/booking_intents/models.py` and create, read, update, and abandon handlers in `apps/api/app/api/v1/booking_intents.py`. Subsequent booking work must extend and validate these existing contracts, preserve their authorization and lifecycle rules, and leave existing booking behavior intact. Do not create a second intent aggregate or duplicate routes.

### Response envelopes

The target V1 contract defines `data`, `meta` and `error` envelopes. Existing accepted V1 endpoints use established response models.

Envelope adoption therefore requires a dedicated compatibility branch with generated-client and browser evidence. It must not be applied as a broad unreviewed breaking change while implementing unrelated domains.

### Manual dispatch

The repository already contains operator-controlled scheduling and assignment logic. New matching, candidate and assignment work must extend that implementation, centralize eligibility/capacity checks, and preserve manual mode. It must not create a parallel dispatch engine or enable automatic assignment.

## Core booking flow

```text
service
→ booking intent
→ address normalization and validation
→ ZIP / ZIP+4 and coordinates
→ service-zone lookup
→ service-address IANA timezone
→ BREERO operating hours
→ eligible provider organizations and professionals
→ provider schedules and exceptions
→ authoritative capacity calculation
→ customer-safe slots
→ 30-minute capacity hold
→ safe client reconciliation
→ booking/request transaction
→ awaiting assignment
→ matching and ranked internal candidates
→ manual dispatch
→ provider job
→ service delivery
→ completion
→ reviews, history and analytics
```

The customer never sees candidate provider identity before the authorized assignment lifecycle permits disclosure.

## Capacity and concurrency contract

Capacity is both job-count and minute capacity. The canonical allocation view accounts for service duration, before/after buffers, travel, existing bookings, active holds, manual blocks, time off, daily job limits, daily minute limits, concurrent-job limits and emergency reserves.

PostgreSQL transaction locks and database constraints are the final safety boundary. Redis cannot be the only hold, booking or capacity lock. Expired holds consume zero capacity even when cleanup workers have not run.

Rescheduling must acquire replacement capacity before releasing a valid existing reservation. Assignment must revalidate eligibility and capacity inside the committing transaction because displayed candidate data may be stale.

## Dependency-ordered branch program

```text
1.  be/auth-identity-tenancy-rbac                    PR #68
2.  be/provider-onboarding-api-completion            PR #85
3.  be/booking-intents-api
4.  be/address-geography-timezone-service-zones
5.  be/provider-services-skills
6.  be/provider-service-areas
7.  be/provider-availability-time-off
8.  be/provider-capacity-ledger
9.  be/booking-capacity-holds
10. be/booking-availability-engine
11. be/booking-request-transaction
12. be/provider-matching-candidates
13. be/manual-assignment-reassignment
14. be/client-booking-cancel-reschedule
15. be/provider-jobs-calendar-team
16. be/trust-documents-compliance
17. be/messaging-notifications-support
18. be/reviews-performance
19. be/leads-featured-placement-disabled-finance
20. fe/client-portal
21. fe/provider-portal
22. fe/admin-dispatch-portal
23. ci/openapi-security-e2e-release-gates
```

Every branch owns one coherent responsibility, its API/OpenAPI changes, authorization and ownership rules, unit/integration/security tests, and rollback or forward-fix evidence.

## Definition of implemented

A route may move from `DECLARED_TARGET_REQUIRES_PROOF` to an implemented status only after all applicable evidence exists:

```text
request and response schemas
authentication
authorization
tenant and ownership scope
input and domain validation
transaction boundary
error contract
audit record
idempotency where required
database concurrency safety where required
outbox event where required
OpenAPI
unit tests
PostgreSQL/PostGIS integration tests
RBAC/security tests
exact-head CI
```

Frontend route existence, a database table, a mock response or a passing render test is not sufficient.

## Protected posture

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
```

Runtime enforcement and zero-side-effect tests remain mandatory before any release is described as safe.
