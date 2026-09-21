# BREERO Marketplace Experience System

Status: **binding product-design authority**

This document extends `docs/design-system.md` from visual governance into a coherent home-services marketplace experience. It preserves the existing BREERO FastAPI/Next.js modular monolith and the current request-first, quote-capable, manually dispatched release boundary.

It does not claim that every domain below is already implemented, deployed, enabled, or production-certified. Product pages may render a capability only when the authoritative backend exposes it and the effective feature/capability state allows it.

## 1. Product promise

BREERO should feel like one coordinated service operating system rather than a directory of disconnected contractors.

The experience must make these questions clear at every step:

1. What service is being requested?
2. Is the service request-only, quote-required, or instant-bookable?
3. Is the address and service area eligible?
4. What provider eligibility and compliance rules apply?
5. Is capacity available, limited, unavailable, or awaiting dispatcher review?
6. What is the current lifecycle state?
7. What action can the current user safely take next?
8. What remains pending and who owns it?

## 2. Product principles

### Truth before conversion

BREERO must never improve conversion by implying a state the backend has not established. Do not show:

- a confirmed provider before assignment;
- a confirmed appointment before the authoritative booking transition;
- a verified badge without current verification evidence;
- a rating without eligible review evidence;
- capacity without the scheduling engine or dispatcher authority;
- a price when the service is quote-required or request-only;
- payment or payout actions while the protected capability is disabled;
- automatic matching or assignment while the release remains manual.

### One lifecycle, multiple workspaces

Customer, provider, worker, dispatcher, support, trust, finance, quality, marketing, sales, and administration views are projections of the same authoritative lifecycle. They must use the same status vocabulary, timestamps, aggregate identifiers, correlation references, and capability state.

### Progressive disclosure

Public discovery should remain simple. Operational and compliance detail appears only when it becomes relevant and authorized. Avoid dense dashboards that expose every future feature at once.

### Evidence-based trust

Trust is shown through specific, dated facts:

- identity status;
- business status;
- license status and expiration;
- insurance status and expiration;
- background-screening status where applicable;
- service qualifications;
- eligible completed-service reviews;
- response and completion history where policy permits.

Do not collapse distinct checks into an unqualified “verified professional” claim.

### Mobile-first service completion

Critical paths must work at 320, 375, 390, and 430 CSS pixels before desktop enhancements are accepted. Forms, drawers, timelines, capacity signals, and dispatch controls must not require horizontal scrolling.

## 3. Experience architecture

### Public website

```text
Home
Services
Service category
Service detail
How BREERO works
Trust and safety
Provider information
Request service
Contact and support
Legal, privacy, accessibility, communication preferences
```

The public website owns discovery and truthful conversion. It does not own authoritative scheduling, provider assignment, pricing calculations, or eligibility decisions.

### Customer marketplace

```text
Overview
Requests
Quotes
Current service
Upcoming services
Past services
Addresses
Messages when enabled
Provider information after authorized disclosure
Reviews when eligible and enabled
Notifications
Profile
Security
Support
Privacy and deletion requests
```

### Provider workspace

```text
Overview
Application and onboarding
Business profile
Services and skills
Service areas and ZIP coverage
Team and workers
Credentials and compliance
Availability and time off
Capacity
Opportunities when enabled
Quotes
Schedule
Jobs
Customers after authorized relationship
Reviews when enabled
Messages when enabled
Notifications
Performance
Security
Help
```

### Worker workspace

```text
Today
Assigned jobs
Job detail
Schedule
Availability
Credentials
Evidence and completion actions
Security
Help
```

### Operations and dispatch

```text
Request queue
Unassigned work
Urgent requests
Sunday emergency
Candidate recommendations
Provider capacity and schedule
Coverage and compliance warnings
Assignment, reassignment, unassignment and escalation
Booking and job oversight
Operational exceptions
Integration delivery and replay
```

### Administration

```text
Dashboard
Users, roles and permissions
Catalog and categories
Pricing configuration
Service areas and ZIP coverage
Operating hours and emergency policy
Provider applications and compliance
Feature flags and capabilities
Audit
Integrations
Analytics
System health
Releases
```

## 4. Shared marketplace components

The following components are exported from `@breero/ui` and are the default patterns for new marketplace screens.

### `MarketplaceServiceCard`

Use for service discovery and category results. It communicates:

- category;
- service title and description;
- pricing mode;
- typical duration when authoritative;
- coverage summary;
- emergency eligibility;
- one real destination.

It must not invent availability or a price.

### `PricingModeBadge`

Supported values:

```text
INSTANT_BOOKABLE
QUOTE_REQUIRED
REQUEST_ONLY
```

The badge reflects catalog policy, not frontend inference.

### `ProviderTrustCard`

Use after the customer or operator is authorized to see a provider candidate or assignment. It presents distinct verification facts, coverage, response information, current capacity state, and verified-service review evidence when supplied.

Omitting review evidence must omit the rating interface entirely.

### `TrustBadge`

Supported facts:

```text
IDENTITY
BUSINESS
LICENSE
INSURANCE
BACKGROUND SCREENING
SERVICE QUALIFICATION
```

Supported states:

```text
VERIFIED
PENDING REVIEW
EXPIRED
NOT REQUIRED
```

### `CapacitySignal`

Supported states:

```text
AVAILABLE
LIMITED
DISPATCHER REVIEW
UNAVAILABLE
```

This component does not create or reserve capacity. It displays an authoritative result or a documented manual-review state.

### `ProjectStatusTimeline`

Use for request, quote, booking, assignment, job, support, compliance, and dispute lifecycles. Exactly one step may use `aria-current="step"`.

Supported presentation states:

```text
COMPLETE
CURRENT
UPCOMING
BLOCKED
```

### `MarketplaceStatePanel`

Every data surface must deliberately support:

```text
LOADING
EMPTY
ERROR
RESTRICTED
DISABLED
SUCCESS
```

A blank card wall is not an acceptable empty or error state.

## 5. Core customer journey

The long-term experience follows this authoritative sequence:

```text
Choose service
→ enter service address
→ normalize and validate address
→ resolve ZIP, coordinates and service-address timezone
→ determine BREERO service zone and rules
→ determine operating hours
→ determine qualified providers
→ evaluate provider schedule and capacity
→ show safe customer choices
→ create an atomic 30-minute capacity hold when applicable
→ collect or reconcile customer identity
→ create request or booking
→ convert or release the hold
→ manual dispatch and assignment under the current release policy
→ service delivery
→ completion
→ eligible review and history
```

The frontend may advance only after the backend confirms the preceding transition.

## 6. Booking, quote, and request language

### Request-only

Use:

```text
Request service
Submit request
Request received
Dispatcher review
Provider assignment pending
```

Do not use “booked,” “confirmed,” or “provider assigned.”

### Quote-required

Use:

```text
Request a quote
Quote under review
Quote ready
Accept quote
Decline quote
Convert accepted quote to booking
```

Quote acceptance does not itself imply payment or provider assignment.

### Instant-bookable

Use only when the authoritative catalog, capacity engine, hold engine, provider eligibility, booking capability, and release policy all permit it.

## 7. Provider discovery and matching presentation

Eligibility filtering must happen before commercial or relevance scoring. The UI may explain candidate facts such as:

- service supported;
- service area matched;
- compliance current;
- schedule match;
- capacity available;
- distance or travel estimate;
- emergency eligibility;
- reliability and eligible review evidence.

Internal score weights and risk scoring are not public customer data. Sponsored placement must never override safety, coverage, licensing, compliance, skill, schedule, or capacity eligibility.

## 8. Dispatch design

The dispatch console must prioritize decisions rather than decoration.

Each work item should expose:

```text
request or booking identifier
customer requested window
service-address timezone
service and duration
coverage result
urgency and Sunday/emergency policy
current assignment state
recommended candidates
capacity and travel facts
compliance warnings
last transition and correlation reference
```

Actions must be explicit and separately authorized:

```text
Assign
Reassign
Unassign
Hold
Release hold
Cancel assignment
View candidates
Contact provider when communication is authorized
Escalate
```

Every action requires a loading state, optimistic-concurrency policy, success confirmation, failure recovery, and audit reason where applicable.

## 9. Forms

Forms must use shared fields and preserve user work across recoverable failures.

Required behavior:

- visible labels and descriptions;
- field-level backend validation;
- error summary for multi-field failure;
- stable idempotency key for an unchanged retry;
- double-submit prevention;
- `Retry-After` handling;
- correlation/reference display;
- capability-aware disabled states;
- no fabricated success state;
- keyboard and screen-reader validation;
- privacy/consent context at the point of collection.

Administrative replacement forms must follow read → review → confirm → write rather than blind overwrite.

## 10. Search, filters, and lists

Production list views use server-side search, sort, filter, date range, status, and pagination. They must not load an entire table into the browser.

Every list provides:

- active filter summary;
- result count when supplied;
- clear/reset action;
- loading skeleton;
- empty result recovery;
- API failure retry;
- stable row/action identity;
- URL or preserved state where useful;
- accessible names for icon-only controls.

## 11. Drawers, dialogs, and destructive actions

Drawers are for inspection or focused editing without losing list context. Dialogs are for short decisions and confirmations.

Required:

- focus moves into the surface;
- Escape closes when safe;
- focus returns to the trigger;
- title and description are programmatically associated;
- stale-record and permission-loss responses are handled;
- destructive actions state the affected resource and consequence;
- capability-disabled actions remain visibly unavailable rather than silently disappearing when explanation is useful.

## 12. Status vocabulary

The UI must use domain status values and explicit presentation mappings. Do not invent a frontend-only state that can be mistaken for persisted business state.

Recommended cross-domain presentation:

```text
Draft
Submitted
Under review
Pending customer
Pending provider
Pending dispatcher
Confirmed
Assigned
In progress
Completed
Cancelled
Expired
Blocked
Failed retryable
Failed terminal
```

Domain-specific state machines remain authoritative.

## 13. Accessibility acceptance

At minimum verify:

- keyboard-only operation;
- visible focus;
- correct heading hierarchy;
- form labels, descriptions and errors;
- live-region/status announcements;
- modal and drawer semantics;
- timeline semantics;
- status not communicated by color alone;
- contrast;
- reduced motion;
- 200% zoom and reflow;
- touch targets;
- Chromium, Firefox, and WebKit.

Automated checks supplement rather than replace manual verification.

## 14. Responsive acceptance

Validate these widths:

```text
320
375
390
430
768
1024
1440+
```

Critical journeys:

```text
service discovery
request intake
login and identity recovery
address entry
quote decision
customer request history
provider onboarding
provider schedule and capacity
worker job actions
dispatch candidate review
admin access and compliance review
```

## 15. Competitive product direction

BREERO should differentiate through operational clarity, not copied layouts or unsupported marketing claims:

1. Show the complete service lifecycle, not only lead submission.
2. Keep request, quote, booking, assignment, and job states visibly distinct.
3. Expose provider eligibility as specific evidence rather than a single vague badge.
4. Make capacity, coverage, timezone, and manual-dispatch ownership understandable.
5. Give customers, providers, workers, and operators one shared status language.
6. Make privacy, consent, support, dispute, and audit paths first-class.
7. Preserve the ability to add matching, messaging, reviews, payments, and sponsored placement without prematurely enabling them.

## 16. Branch and review rules

Design work stays in `fe/enterprise-design-governance` or a narrowly scoped child branch. Heavy product domains remain separate implementation branches.

A design PR is not complete until its exact head passes:

```text
frozen install
frontend dependency audit
lint
typecheck
unit/component tests
API contract check
production build
Chromium/Firefox/WebKit E2E
design-system guard
accessibility and responsive evidence for affected journeys
fresh independent review
zero unresolved review threads
```

No design PR deploys, migrates production data, writes DNS/Caddy configuration, or activates protected capabilities.
