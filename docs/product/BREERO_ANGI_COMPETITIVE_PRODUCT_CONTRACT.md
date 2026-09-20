# BREERO Angi-Competitive Product Contract

Status: **product target, experiment and claim authority**

BREERO may target a better customer, provider and operator experience than Angi. It must not make a general or feature-specific superiority claim until the exact released system passes the reproducible method below and legal/marketing approves the final wording.

Research basis reviewed on 2026-08-27: Angi's official public descriptions of project intake, eligible instant booking/upfront pricing, quote comparison, reviews, provider screening language, support/guarantee, professional onboarding and AI project assistance.

## 1. Competitive baseline to match

BREERO must eventually provide a coherent version of:

```text
service and project discovery
structured project intake
request-only, quote-required and eligible instant-bookable modes
provider discovery or matching
provider trust/review evidence
quote review and customer decision
clear support and issue-resolution path
provider onboarding and business tooling
mobile-first customer experience
project-scope assistance
```

Feature parity alone is not superiority.

## 2. BREERO differentiation

### Full lifecycle transparency

```text
REQUEST
→ ADDRESS / COVERAGE
→ QUOTE OR CAPACITY REVIEW
→ HOLD WHEN APPLICABLE
→ MANUAL DISPATCH
→ PROVIDER ASSIGNMENT
→ SERVICE DELIVERY
→ COMPLETION
→ REVIEW / HISTORY
```

Every pending state names its owner and next action.

### Specific trust evidence

```text
identity
business
license and expiration
insurance and expiration
background screening where applicable
service qualifications
eligible completed-service reviews
```

Pending and expired evidence remain distinct and affect eligibility under policy.

### Capacity-aware marketplace

Capacity is authoritative backend state built from service duration, buffers, travel estimate, existing work, holds, blocks, time off, limits and emergency reserves. It is never inferred from a provider profile or calculated only in the browser.

### Address, ZIP, zone and timezone correctness

```text
normalized address
ZIP / ZIP+4
city / state / county
coordinates
IANA service-address timezone
BREERO service zone
provider coverage
operating-hours and emergency policy
```

### Real dispatch operations

Operators receive eligibility, capacity, travel, compliance, coverage, requested-window, timezone and assignment-history evidence. Current assignment remains manual.

### Provider and worker operating system

Providers receive organization/team, services/skills, coverage, schedule, capacity, compliance, quotes, jobs, authorized customer relationships, performance, security and support. Workers receive an assignment-focused experience separate from provider administration.

### Support, trust and dispute layer

Support cases, compliance, moderation, disputes, operational exceptions, integration failures and audit are first-class workflows.

### Privacy-preserving communication

Customer PII disclosure follows lifecycle purpose. Providers do not receive unrestricted contact, address, conversation or document access before an authorized relationship exists.

### Explainable recommendations

Eligibility and scoring remain separate. Commercial sponsorship cannot override safety, qualification, coverage, schedule, capacity or compliance.

### Operational reliability

```text
transactional outbox
durable authenticated inbox
idempotency
per-claim ownership
retry/backoff
terminal failure visibility
manual replay authorization
reconciliation
```

## 3. Optional AI assistance boundary

AI project assistance belongs in separate branches after catalog, request, address, identity/privacy, quote and API-contract foundations are accepted.

Allowed initial uses:

```text
clarify customer description
suggest an existing catalog category
identify missing intake information
summarize customer-provided scope
explain next steps
prepare an operator draft
```

AI cannot authoritatively approve/verify a provider, verify compliance, promise a price, create capacity, accept a quote, assign a provider, confirm a booking, approve a change order, make a payment decision, expose private data or activate a feature.

Every accepted result passes deterministic validation and a normal authorized domain command.

## 4. Frozen comparison baseline

Before a comparative study:

1. Record the exact BREERO source SHA, image digest, configuration/capability snapshot and environment.
2. Record the Angi product surfaces and official public descriptions used as the comparison baseline no more than 30 days before testing.
3. Preserve dated screenshots/session recordings, task URLs, device/browser, geography and service category in a restricted research archive.
4. Freeze task scripts, hypotheses, primary metrics, exclusion rules and statistical method before collecting results.
5. Do not change either task script or BREERO candidate after the study starts; a code push requires a new study version.

A changed competitor surface or changed BREERO SHA invalidates stale evidence for the affected journey.

## 5. Comparable journeys

The minimum customer comparison includes identical neutral scenarios for:

```text
find an appropriate service
understand request-only vs quote vs eligible booking
submit a service request
understand provider trust evidence
review/compare quotes where supported
find current request/project state
find support/cancellation/rescheduling information
complete the critical flow on mobile
```

Provider comparison includes:

```text
understand provider eligibility and approval
start and complete onboarding
add services/coverage
understand lead/opportunity or job state
find schedule/capacity/compliance requirements
find support/security controls
```

A feature not available in both products is reported as capability coverage, not forced into a misleading task-time comparison.

## 6. Study design

### Participants and cohorts

Use neutral recruitment, not employees or existing design contributors.

Minimum unless a preregistered power analysis requires more:

```text
CUSTOMER=100 completed sessions per product
PROVIDER=60 completed sessions per product
SERVICE_CATEGORIES>=4
GEOGRAPHIES>=4
MOBILE_SHARE>=50%
ACCESSIBILITY_COHORT>=10 users relying on assistive technology across the study
```

Use randomized, stratified, between-subject assignment by product, device, service category, geography and prior marketplace experience. Moderator assistance is counted as task failure for the primary completion metric.

### Primary customer metrics and formulas

```text
TASK_COMPLETION = completed without moderator rescue / started eligible sessions
MEDIAN_TASK_TIME = median seconds among completed sessions
CRITICAL_ERROR_RATE = sessions with wrong, unsafe or unrecoverable outcome / started eligible sessions
CLARITY_SCORE = mean post-task response on a fixed 1–7 scale
TRUST_SCORE = mean post-task response on a fixed 1–7 scale
```

Secondary metrics:

```text
form validation recovery
backtracking
support-intent rate
mobile overflow/blocker rate
keyboard/screen-reader task completion
```

### Provider metrics and formulas

```text
ONBOARDING_COMPLETION = completed required onboarding / started eligible sessions
MEDIAN_ONBOARDING_TIME = median seconds among completed sessions
REQUIREMENT_COMPREHENSION = correct answers / fixed requirement questions
PROVIDER_TRUST_SCORE = mean fixed 1–7 post-task scale
```

### Analysis

Report absolute differences, relative differences where meaningful, 95% confidence intervals, sample sizes, exclusions and missing data. Use the preregistered statistical test appropriate to the metric; do not select tests after seeing results.

## 7. Reproducible superiority decision

### Mandatory safety and parity gates

All must pass:

```text
zero fabricated marketplace state in tested journeys
zero cross-tenant/ownership exposure
zero duplicate authoritative booking/request from retry/race tests
zero unauthorized protected-capability activation
zero critical/serious accessibility findings on critical journeys
complete request/quote/booking/assignment history where applicable
exact-head CI and browser matrix pass
```

BREERO must also support every competitor capability explicitly included in the claim scope or clearly disclose that the claim excludes it.

### Non-inferiority guardrails

No primary customer metric may be materially worse:

```text
TASK_COMPLETION lower 95% confidence bound for BREERO-Angi >= -3 percentage points
MEDIAN_TASK_TIME upper 95% confidence bound for BREERO/Angi ratio <= 1.10
CRITICAL_ERROR_RATE upper 95% confidence bound for BREERO-Angi <= +2 percentage points
CLARITY_SCORE lower 95% confidence bound for BREERO-Angi >= -0.25 on 1–7 scale
TRUST_SCORE lower 95% confidence bound for BREERO-Angi >= -0.25 on 1–7 scale
```

### Customer-experience superiority

BREERO passes customer-experience superiority only when at least **three of five** primary metrics meet their threshold and none violates a guardrail:

```text
TASK_COMPLETION lower 95% confidence bound >= +5 percentage points
MEDIAN_TASK_TIME upper 95% confidence bound for ratio <= 0.85
CRITICAL_ERROR_RATE upper 95% confidence bound <= -3 percentage points and relative reduction >= 25%
CLARITY_SCORE lower 95% confidence bound >= +0.50 on 1–7 scale
TRUST_SCORE lower 95% confidence bound >= +0.50 on 1–7 scale
```

### Provider-experience superiority

BREERO passes provider-experience superiority only when at least **two of four** provider metrics meet their threshold and none is materially worse:

```text
ONBOARDING_COMPLETION lower 95% confidence bound >= +5 percentage points
MEDIAN_ONBOARDING_TIME upper 95% confidence bound for ratio <= 0.85
REQUIREMENT_COMPREHENSION lower 95% confidence bound >= +10 percentage points
PROVIDER_TRUST_SCORE lower 95% confidence bound >= +0.50 on 1–7 scale
```

Non-inferiority margins for provider metrics are -3 percentage points for completion, 1.10 time ratio, -5 percentage points for comprehension and -0.25 for trust.

### Allowed claim scope

```text
"Better customer experience" requires customer superiority only.
"Better provider onboarding experience" requires provider superiority only.
A general "better than Angi" claim requires both customer and provider superiority, all safety/parity gates, and legal/marketing approval.
```

Operations metrics cannot support a public competitor comparison unless equivalent competitor data is lawfully and reliably available. Otherwise they support only internal BREERO release decisions.

## 8. Production observation gate

A controlled study supports UX claims but not operational reliability claims.

Before any operational marketplace claim, observe the exact production release for at least:

```text
90 consecutive days
and
1,000 eligible customer requests
and
100 completed eligible services
```

Use the longer requirement when one threshold is reached first. Segment by service category, geography, device and new/repeat customer. Publish the observation window and denominator.

Required internal operational guardrails:

```text
cross-tenant exposure=0
duplicate authoritative bookings from retry/race=0
unauthorized capability activation=0
critical accessibility regression=0
PII leakage incident=0
unreconciled financial mutation=0
backup restore rehearsal=PASS
worker/queue/integration health=OBSERVED
```

Time-to-response, assignment, conversion, cancellation, support, provider acceptance/utilization and repeat-rate targets are set before the release based on BREERO's prior cohort. They are not presented as Angi comparisons without equivalent reliable competitor data.

## 9. Data sources and auditability

```text
instrumented BREERO product events without unnecessary PII
research session recordings and task logs
fixed post-task questionnaires
provider onboarding events
support-case and operational-exception data
exact release/configuration manifests
dated official Angi baseline evidence
```

Store analysis code, anonymized aggregate data, metric dictionary, exclusions and final report under approved privacy/retention controls. An independent reviewer must be able to reproduce the decision.

## 10. UX acceptance

Every competitive journey includes loading, empty, error, restricted, disabled, success, applicable search/filter/sort/pagination, forms/validation, drawers/dialogs, mobile, keyboard, screen-reader semantics, reduced motion and Chromium/Firefox/WebKit.

No button exists without a real action, real route or explicit unavailable/overview-only explanation.

## 11. Protected activation posture

```text
AUTO_ASSIGN_PROVIDER=false
AUTO_CONFIRM_BOOKING=false
PAYMENTS_ENABLED=false
LIVE_PROVIDER_DISPATCH=false
LIVE_EMAIL_DELIVERY=false
LIVE_SMS_DELIVERY=false
MESSAGING_ENABLED=false
REVIEWS_ENABLED=false
FEATURED_PROVIDERS_ENABLED=false
```

Implementation readiness and production activation remain separate changes. Runtime kill switches must be implemented and tested; documentation values alone are insufficient.

## 12. Current status

```text
COMPETITIVE_TARGET=DEFINED
COMPARISON_METHOD=DEFINED
DESIGN_SYSTEM=PR_67
DASHBOARD_INTERACTIONS=PR_69
IDENTITY_RBAC=PR_68
FULL_MARKETPLACE_IMPLEMENTED=NO
CONTROLLED_COMPARISON_COMPLETED=NO
PRODUCTION_OBSERVATION_COMPLETED=NO
STAGING_CERTIFIED=NO
PRODUCTION_DEPLOYED=NO
PUBLIC_SUPERIORITY_CLAIM=NOT_AUTHORIZED
```
