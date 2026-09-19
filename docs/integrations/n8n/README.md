# Breero marketplace ↔ Middleware ↔ n8n integration

## Authority

Breero owns marketplace customers, providers, leads, jobs, quotes, assignments, commercial rules and marketplace state. Middleware is the cross-system command and event boundary. n8n sequences approved workflows only.

n8n never writes directly to the Breero database, Odoo, Keycloak administration, Klyrow/Postal, Telnexa/Jasmin, payment processors, provider systems or another marketplace service.

```text
Breero domain transaction + outbox
  -> Middleware authenticated inbox
  -> canonical automation job
  -> n8n routing, timing and human review
  -> governed Middleware command
  -> Breero API or approved adapter
  -> destination read-back
  -> Middleware reconciliation
  -> Breero/Odoo projection
```

## Events available to automation

```text
breero.customer.created
breero.provider.created
breero.provider.review_required
breero.provider.approved
breero.lead.created
breero.lead.qualified
breero.quote.requested
breero.quote.received
breero.provider.assignment_requested
breero.provider.assigned
breero.job.created
breero.job.status_changed
breero.job.exception
breero.payment.status_changed
breero.review.created
```

Events are committed through a transactional outbox with the marketplace state change.

## Commands requested through Middleware

```text
breero.lead.route_plan
breero.lead.create_review
breero.provider.create_review
breero.provider.activate_approved
breero.quote.request
breero.quote.reconcile
breero.job.assign_provider
breero.job.create_task
breero.job.escalate_exception
breero.customer.notification_request
breero.provider.notification_request
breero.odoo_projection.reconcile
```

The assignment command does not accept an n8n-selected provider without Breero authorization and concurrency checks. Duplicate assignment requests return the existing result or a stable conflict.

## Initial n8n workflows

```text
breero.marketplace.lead-route.v1
breero.marketplace.provider-onboarding.v1
breero.marketplace.quote-received.v1
breero.marketplace.provider-assign.v1
breero.marketplace.job-exception.v1
```

## Human review and safety

- Provider onboarding and low-confidence lead routing require human review.
- Financial, payout or payment effects are outside n8n and remain separately gated.
- n8n cannot bypass quote versioning, job state transitions, provider eligibility, tenant isolation, idempotency or optimistic concurrency.
- Odoo receives approved projections through Middleware and is not the marketplace authority.
- Email and SMS are requested through Middleware; provider credentials never enter n8n.
- Cross-tenant leads, quotes, providers and jobs are inaccessible.

## Capability freeze

```text
BREERO_WRITE=false
LEAD_PUBLISH=false
PROVIDER_ASSIGNMENT=false
PAYMENT_EXECUTION=false
ENABLE_EXTERNAL_DELIVERY=false
DEAD_LETTER_REPLAY=false
```

## Branch dependencies

```text
Breero.com/main
Middleware-/core/integration-contracts
Middleware-/core/event-ledger-outbox
Middleware-/core/webhook-inbox-replay
Middleware-/core/workers-scheduler
Middleware-/integration/keycloak
Middleware-/integration/n8n
N8N/contract/automation-control-plane-v2-20260827
N8N/shared/automation-runtime
N8N/automation/breero-marketplace
```

## Acceptance

```text
DIRECT_N8N_DATABASE_ACCESS=DENIED
DIRECT_N8N_PROVIDER_ACCESS=DENIED
TENANT_ISOLATION=PASS
QUOTE_AND_JOB_CONCURRENCY=PASS
EXACT_REPLAY=PASS
CONFLICTING_REPLAY=PASS
DUPLICATE_ASSIGNMENT_SAFE=PASS
HUMAN_REVIEW_PATH=PASS
LIVE_MARKETPLACE_EFFECTS=DISABLED
WORKFLOWS_ACTIVE_IN_GIT=NO
PRODUCTION_CHANGED=NO
```
