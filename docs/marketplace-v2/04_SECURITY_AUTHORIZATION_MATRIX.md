# BREERO Marketplace V2 — Security and Authorization Matrix

## Status

Binding deny-by-default authorization authority for Marketplace V2 implementation.

A role name, frontend route, Keycloak claim, CRM assignment, feature flag name, or possession of a record identifier is never sufficient by itself. Every protected command and query must enforce the complete server-side decision described here.

## Authorization decision

```text
valid authenticated Principal
AND required permission
AND active tenant/legal-entity membership
AND record policy
AND resource state permits operation
AND required runtime capability is effective
AND any command preconditions are satisfied
= ALLOW
```

Anything else is denied.

For private resources, return `404` instead of `403` where revealing existence would expose cross-tenant, cross-provider, cross-customer, unmatched-provider, or otherwise private information.

## Principal authority

A server-constructed `Principal` may contain:

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

Rules:

- production identity is bound by immutable `(issuer, subject)` mapping;
- email is profile data, not an identity key;
- Keycloak role claims may be inputs, but BREERO membership and record policy remain authoritative;
- no browser-provided tenant, provider, worker, role, or permission value is trusted;
- no wildcard application role grants every permission;
- suspended, expired, removed, or inactive memberships fail closed.

## Permission catalog

Initial permission authority:

```text
project_request.read
project_request.create
project_request.update
project_request.submit
project_request.cancel

matching.run
matching.inspect

opportunity.read
opportunity.respond
opportunity.manage

lead_connection.read
lead_connection.manage

quote.read
quote.create
quote.revise
quote.send
quote.accept

conversation.read
conversation.send

booking.read
booking.create
booking.reschedule
booking.cancel
booking.confirm.manual

job.read
job.assign
job.execute
job.complete
job.cancel

provider.read
provider.manage
provider.members.manage
provider.credentials.manage
provider.credentials.verify
provider.suspend

review.create
review.respond
review.moderate

dispute.create
dispute.read
dispute.manage

integration.read
integration.retry
integration.replay

`integration.retry` controls eligible outbound delivery retries only. Manual durable-inbox replay requires `integration.replay`; retry-only principals cannot replay inbound provider events.

operations.exception.read
operations.exception.manage

finance.refund
finance.payout.prepare
finance.payout.approve
finance.reconcile

admin.users.manage
admin.roles.manage
admin.features.manage
admin.audit.read
admin.releases.manage
```

`quote.accept` is the canonical customer quote-decision permission across the authorization matrix, API contract registry, implementation package, tests, seeds, and admin surfaces. It covers the authorized accept/decline decision command unless a later reviewed ADR deliberately separates those actions. Do not introduce `quote.decide` in parallel.

Permission names authorize an action class only. Record policy and capability checks still apply.

## Role and resource matrix

| Actor | Allowed scope | Representative allowed actions | Explicit denials / separation of duty |
|---|---|---|---|
| Customer | Own customer identity and own lifecycle records | Create/update/submit/cancel own ProjectRequest; read own quote/booking/job; accept or decline own quote; send in own authorized conversation; create review only after verified eligible completion; create/read own dispute | No other customer records; no provider-private data; no matching internals; no assignment; no credential, finance, feature, integration, or admin authority |
| Provider Owner | Active provider organizations for which the user has an active owner membership | Manage provider profile, members, workers, services, areas, availability, credentials submission, opportunities, quotes, provider-side jobs and responses when separately permitted | Cannot self-verify credentials, suspend providers, approve payouts/refunds, view unmatched customer PII, access another provider, or activate capabilities |
| Provider Manager | Active provider organizations explicitly assigned through membership | Same resource families as Provider Owner but limited to granted permissions and assigned organization scope | Ownership role is not implied; no membership administration, finance, credential verification, suspension, or other-provider access unless separately granted |
| Worker | Own worker profile plus jobs currently assigned through an eligible provider relationship | Read assigned jobs, manage own availability, submit own credentials, perform approved job transitions/evidence actions | No unassigned jobs, unmatched customer PII, provider administration, quote authority, matching, credential verification, finance, or capability authority |
| Dispatcher / Operations | Explicitly assigned tenant/legal-entity operational scope | Inspect/run approved matching, manage operational assignment, bookings/jobs, queues and exceptions through normal commands | No refund/payout approval, credential verification, global user/role management, secret access, or capability activation unless a separate permission is granted and policy allows it |
| Customer Support | Explicit case/campaign/tenant scope needed to assist a customer or provider | Read limited operational projection, create approved notes/activities, initiate approved support commands | No ambient access to all PII, credentials, private mailboxes, finance, matching authority, provider suspension, or admin configuration |
| Trust & Safety | Explicit tenant/legal-entity trust scope | Verify/reject credentials, suspend/reactivate providers through policy, moderate reviews, manage trust disputes | No refund/payout approval, campaign-send authority, integration-secret access, or general system administration |
| Finance | Explicit financial tenant/legal-entity scope | Prepare/refund/reconcile and approve payout operations only through financial commands and dual-control policy | No dispatcher/job assignment, credential verification, trust moderation, unrelated CRM/mailbox access, feature activation, or secret access |
| Admin | Explicit administrative permissions and tenant/legal-entity scope | Manage approved users, roles, catalog/configuration, audit visibility and releases according to granted permissions | `ADMIN` is not a wildcard; no automatic finance, trust, operations, raw-secret, or cross-tenant authority |
| Super Admin | Break-glass or narrowly controlled global administration where explicitly implemented | Only operations documented in an approved break-glass policy with strong authentication, reason, audit and time-bounded access | Never an undocumented wildcard; no bypass of immutable audit, financial dual control, capability/release approval, or tenant isolation |
| Machine principal | Exact registered client, audience, tenant and allowlisted integration purpose | Invoke only the documented machine endpoint/command with client-credentials identity and scoped permission | No human impersonation, browser flow, arbitrary tenant selection, direct database write, undocumented event type, or capability activation |

## Record policies by aggregate

### ProjectRequest

- customer access requires ownership;
- support/ops access requires explicit tenant/legal-entity permission and a valid operational purpose;
- providers do not receive private request/contact data merely because they are service-capable;
- provider visibility begins only through an authorized opportunity/LeadConnection policy.

### Provider, membership and worker

- provider users require an active membership for the exact provider organization;
- provider managers receive only granted permissions;
- workers require the exact worker identity and provider relationship;
- credentials may be submitted by the subject/provider but verified only by an authorized Trust & Safety principal;
- suspended or ineligible providers/workers cannot accept new work.

### Matching, Opportunity and LeadConnection

- matching candidates/results are private operations state unless a specific projection is approved;
- a provider may read/respond only to an opportunity addressed to that provider;
- opportunity acceptance does not itself authorize unrestricted customer contact data;
- a LeadConnection must be valid and in a state that permits the requested disclosure/action;
- paid-lead charging is a separate disabled financial capability and is never implied by connection creation.

### Quote and Conversation

- provider quote access requires provider membership plus relationship to the exact opportunity/LeadConnection;
- customer quote access requires ownership through the exact request/connection;
- only the quote author/provider side may create or revise; only the owning customer with `quote.accept` may accept or decline;
- messaging requires the messaging capability, an active authorized conversation, and record policy;
- email/SMS transport never grants conversation authority.

### Booking and Job

- customer access requires ownership;
- provider access requires the exact provider assignment/relationship;
- worker access requires current eligible assignment;
- manual confirmation requires `booking.confirm.manual` and the operations policy;
- automatic booking, assignment and confirmation remain denied unless separately implemented, tested, approved and enabled;
- job transitions must satisfy state machine, actor, assignment, version and capability rules.

### Review and Dispute

- review creation requires an eligible verified completed job and the owning customer;
- provider response requires the reviewed provider relationship;
- moderation is separate from provider/customer actions;
- dispute access is limited to involved parties and explicitly authorized operations/trust roles;
- supporting evidence follows private-object authorization.

### Financial records

- payment, refund, earning and payout access requires separate finance permissions and exact tenant/legal-entity scope;
- payout preparation and payout approval must use different principals where dual control is required;
- browser redirects, CRM stages, provider dashboards and manual database edits are not authoritative settlement evidence;
- financial capabilities remain disabled until their dedicated implementation and activation gates pass.

## PII disclosure policy

```text
public discovery
→ public provider/catalog data only

qualified request before provider relationship
→ no direct customer contact disclosure

authorized Opportunity
→ minimum information needed to evaluate, still masked where policy requires

active LeadConnection / assigned Job
→ only approved contact/address fields needed for the lifecycle action

closed/expired/cancelled relationship
→ disclosure removed or reduced according to retention and support policy
```

Precise address, phone, email, access instructions, credential documents and financial data require explicit field-level purpose. Logs, events, analytics and CRM projections must use redaction/allowlists.

## Capability separation

A capability is not a role and a role is not a capability.

Commands for matching, provider self-service, opportunities, messaging, reviews, instant/automatic booking, assignment, confirmation, payments, payouts, paid leads, marketing and unrestricted external sends must fail closed when the corresponding capability is absent, false, unreadable or not approved for the environment.

Capability evaluation happens server-side for every command. Frontend visibility is advisory UX only.

## Integration and webhook authorization

Every inbound integration must prove:

```text
registered provider/client
approved endpoint/event type
signature or token validity
timestamp/replay policy
provider/event uniqueness
tenant/legal-entity mapping
translator allowlist
command permission and record policy
```

Webhook receipt is not authorization to mutate arbitrary state. Verified payloads enter the durable inbox; a worker/translator invokes the normal authorized domain command path.

## Command enforcement order

For a protected mutation:

```text
1. validate authentication and construct Principal
2. resolve authoritative tenant/legal-entity/provider/worker context
3. require permission
4. apply record policy without loading an arbitrary cross-tenant record where avoidable
5. require capability
6. validate idempotency identity and request hash
7. validate If-Match/version and domain transition
8. commit business state + history + audit + idempotency + outbox atomically
```

No external provider call belongs inside the authoritative transaction.

## Mandatory negative tests

At minimum:

```text
wrong issuer/audience/azp/algorithm
expired/not-yet-valid/malformed/missing token
unknown kid refresh then rejection
local production authentication denied
inactive/removed membership denied
cross-tenant and cross-legal-entity denial
cross-customer ProjectRequest/Quote/Booking/Job denial
cross-provider profile/opportunity/quote/conversation/job denial
unmatched-provider customer PII denial
worker denied unassigned job and other-worker credentials
expired credential and suspended-provider denial
support denied unrelated PII/private mailbox
ops denied refund/payout approval
finance denied dispatch/credential verification
provider denied self-verification and suspension
customer denied review before eligible completion
missing/false/unreadable capability denied
stale If-Match denied
idempotency key with different payload denied
machine client denied undocumented endpoint/tenant/event
private resource non-enumeration behavior
```

Tests must run against PostgreSQL/PostGIS where policy depends on persisted membership, uniqueness, locking, geometry or row-level relationships.

## Review evidence

Every authorization-affecting PR must provide:

- changed permission and record-policy inventory;
- affected endpoint/command matrix;
- positive and negative tests;
- tenant/legal-entity isolation evidence;
- PII/classification impact;
- capability interaction;
- migration/backfill/rollback evidence when membership or identity schema changes;
- exact final SHA and required CI results;
- unresolved risk statement.

Documentation completion alone does not implement or certify these controls.
