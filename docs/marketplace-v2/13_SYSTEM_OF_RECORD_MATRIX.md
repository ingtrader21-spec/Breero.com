# BREERO Marketplace V2 — System of Record Matrix

## Status

Binding authority matrix for Marketplace V2. If another document or integration implies a different owner for a business aggregate, this matrix and `00_PRODUCTION_BLUEPRINT.md` control unless an approved ADR explicitly changes one boundary without weakening unrelated controls.

## Core rule

**BREERO PostgreSQL/PostGIS is authoritative for marketplace business state.**

External systems may execute transport, communication, CRM, automation, identity, payment or provider functions, but they do not become authoritative for marketplace aggregates merely because they contain a projection or provider-side representation.

## Authority matrix

| Data / capability | Authoritative system | Allowed projection / consumer | Projection limits / notes |
|---|---|---|---|
| Public catalog/service content | BREERO | Web, partner, ops, admin, approved CRM/marketing projection | Public fields only |
| Capability state | BREERO Capability Service + approved production configuration | Frontends, ops/admin, middleware | Consumers may project; they may not independently enable a disabled capability |
| Customer user identity binding | BREERO local user + external identity mapping; Keycloak authoritative for OIDC identity assertion | Frontends, audit, approved CRM projection | Email is profile data, not identity key |
| Provider user identity binding | BREERO local user + external identity mapping; Keycloak authoritative for OIDC identity assertion | Partner/admin/ops | Same `(issuer, subject)` rules |
| Roles, memberships and effective marketplace permissions | BREERO | Frontends, audit | Keycloak role claims may be inputs but record-level marketplace authorization remains BREERO policy |
| Customer profile | BREERO | Odoo minimum CRM projection; Codestra/n8n only when approved | Classification policy controls fields |
| Customer address / property | BREERO/PostGIS | Provider/worker only when authorized by lifecycle; Odoo summary if approved | Precise address must not be broadly projected |
| ProjectRequest | BREERO | Odoo summary, ops, provider opportunity projections after policy | Odoo cannot mutate authoritative state directly |
| Qualification/serviceability decision | BREERO domain + PostGIS/provider-neutral geocoding inputs | Ops, CRM status | Geocoder supplies normalized location; BREERO decides eligibility |
| Service area geometry | BREERO/PostGIS | Public/partner projections as approved | External geocoder is not serviceability authority |
| Provider business profile | BREERO | Public profile, Odoo recruitment/CRM projection | Public/private fields separated by classification |
| Provider membership | BREERO | Partner/admin/ops | Odoo/Keycloak do not own provider membership state |
| Worker profile/assignment eligibility | BREERO | Partner/ops | Worker identity may be asserted by Keycloak; assignment eligibility is BREERO state |
| Provider credentials/licensing/insurance metadata | BREERO | Ops/admin status projection | Raw evidence remains private object storage; CRM receives status only unless explicitly approved |
| Provider credential evidence files | BREERO metadata + private object storage | Authorized ops/admin reviewers | No CRM/public projection of raw documents by default |
| Availability/capacity | BREERO | Partner/ops/customer availability projection | External calendar integration may be an input only if approved |
| Matching run/result | BREERO | Ops/provider opportunity projection | External workflow/CRM cannot author matching truth |
| Opportunity | BREERO | Partner portal, Odoo summary if needed | Acceptance/decline must return through authorized command path |
| LeadConnection | BREERO | Partner/customer/ops, approved CRM summary | Paid-lead charging remains separate gated financial capability |
| Conversation/message metadata | BREERO | Customer/provider portals, ops as authorized | Email/SMS providers transport notifications; they are not conversation authority |
| Quote | BREERO | Customer/provider portals, Odoo summary | Price/terms authoritative only from BREERO quote state |
| Booking | BREERO | Customer/provider/ops, Odoo summary | Browser redirect/provider UI never authoritative |
| Job | BREERO | Customer/provider/worker/ops, Odoo summary | All transitions through BREERO state machine |
| Job evidence | BREERO metadata + private object storage | Authorized parties by policy | Only CLEAN files attach to job |
| Review | BREERO | Public/partner/customer/ops as policy permits | Review provider/widget never authoritative unless explicitly designed as adapter input |
| Dispute | BREERO | Customer/provider/ops/admin as authorized | Supporting files private; outcome through domain command |
| Notification intent/state | BREERO | Ops/admin, provider delivery systems | Klyrow/Telnexa return delivery status through inbox |
| Email delivery transport state | Klyrow for provider-side delivery event; BREERO inbox/notification delivery record authoritative for platform state | BREERO notifications/ops | Provider callback verified/idempotent |
| SMS delivery transport state | Telnexa for provider-side delivery event; BREERO inbox/notification delivery record authoritative for platform state | BREERO notifications/ops | Same durable inbox rule |
| Odoo CRM campaign/stage/activities/agent notes | Odoo | BREERO receives only approved callbacks/projections where needed | Odoo owns CRM workflow only, not marketplace lifecycle |
| n8n workflow execution state | n8n | Ops/monitoring as approved | n8n may not directly mutate BREERO business tables |
| Codestra/Kong/middleware routing/delivery transport | Codestra/Kong/middleware | BREERO outbox/ops receives delivery result | Middleware is transport/control plane, not business state owner |
| Redis cache/rate-limit/temporary lock/circuit state | Redis for ephemeral state only | API/workers | Must be reconstructable/disposable; never authoritative marketplace truth |
| Integration outbox event | BREERO PostgreSQL | Workers/middleware/providers | Authoritative delivery state recorded in BREERO |
| Integration inbox event | BREERO PostgreSQL | Inbox workers/translators | Provider event payload/auth evidence retained per policy |
| Audit event | BREERO append-only audit store | Ops/security/admin read-only surfaces | No downstream system may alter canonical audit history |
| Operational exception | BREERO | Ops/admin, optional CRM task projection | Resolution authoritative only through BREERO command |
| Production configuration/capability approval | BREERO controlled config/release governance | Runtime services, ops/admin | Secret values remain in secret manager, not config history |
| Production secrets | Approved secret manager/KMS/Vault-equivalent | Authorized runtime identities only | Git, logs, frontend, CRM and event payloads prohibited |
| Uploaded object bytes | Approved private object storage | Authorized BREERO services/users via short-lived access | Metadata/state authoritative in BREERO; object provider does not decide business use |
| Malware scan verdict | Scanner provider produces verdict; BREERO storage object state is authoritative for use eligibility | BREERO upload workflow | Async callback enters durable inbox |
| Geocoding result | Geocoder produces normalized coordinates; BREERO persists accepted normalized result | BREERO/PostGIS | Geocoder does not determine serviceability |
| Payment provider transaction | Payment provider authoritative for provider-side settlement event; BREERO payment aggregate/journal authoritative for marketplace state | Customer/ops/finance | Signed webhook/reconciliation required; browser redirect never authoritative |
| Refund provider transaction | Payment provider authoritative for provider-side refund event; BREERO refund aggregate/journal authoritative for marketplace state | Ops/finance/customer status | Ambiguous result enters reconciliation state |
| Provider earning/compensation snapshot | BREERO | Partner/finance/ops | Immutable snapshot after authoritative accrual |
| Payout provider transfer | Payout provider authoritative for provider-side transfer result; BREERO payout aggregate/journal authoritative for platform state | Partner/finance/ops | Dual control + idempotency/reconciliation required |
| Financial journal | BREERO append-only journal | Finance/ops/reporting | Corrections are compensating entries, not edits |
| Provider statement/reconciliation evidence | BREERO reconciliation record + imported/provider evidence | Finance/ops | Provider statement is evidence, not a direct overwrite of BREERO state |
| Release source SHA/image digest/SBOM/provenance | GitHub/registry/CI artifacts as immutable build evidence; BREERO release record binds exact candidate | Deployment/readiness tooling | Production release must match certified digest/configuration |
| Launch approval | BREERO/release governance durable approval record | Deployment/readiness tooling | Approval valid only for exact release/config/evidence snapshot |

## Projection contract

Every non-trivial projection must define:

```text
source authority
projection destination
purpose
field allowlist
classification
transformation/redaction
idempotency identity
refresh/event strategy
retention/deletion behavior
failure/degraded behavior
```

A projection is not allowed to write back to its source aggregate except through an approved authenticated integration command/API.

## Odoo boundary

Odoo may own:

```text
campaign
CRM stage
agent assignment inside CRM workflow
activities
approved agent notes
disposition
follow-up
campaign mailbox state
CRM reporting
```

Odoo must not own:

```text
ProjectRequest state
matching result
Opportunity state
LeadConnection state
Quote state
Conversation authority
Booking state
Job state
provider eligibility
credential verification truth
Review state
Dispute state
payment/refund state
earning/payout state
capability activation
```

If an agent action in Odoo needs to change marketplace state, Odoo emits an authenticated approved command request that is processed by the normal BREERO authorization/policy/state/idempotency/audit/outbox path.

## Codestra/Kong/middleware boundary

Codestra/Kong/middleware may:

- authenticate/route approved machine traffic;
- transport events/commands to approved destinations;
- enforce transport-level policy;
- surface delivery result/health.

It must not:

- directly update BREERO business tables;
- invent authoritative marketplace state;
- bypass BREERO record authorization;
- activate a BREERO capability;
- reinterpret an event into an undocumented business mutation.

## n8n boundary

n8n may execute allowlisted workflows against approved APIs/adapters. It must not connect directly with write authority to BREERO business tables.

Workflow state is not business state. If a workflow fails after BREERO commits a transaction, recovery occurs through the outbox/inbox/operational exception mechanism rather than by rewriting the business row from n8n.

## Payment and payout authority

When financial capabilities are later enabled:

```text
provider-side event/statement
→ authenticated webhook or reconciliation input
→ durable inbox/reconciliation record
→ authorized financial command
→ BREERO aggregate + financial journal + audit + outbox
```

No provider dashboard screenshot, browser redirect, client-side callback, CRM stage, or manual database edit is authoritative payment/payout confirmation.

## Conflict rule

When two systems disagree:

1. Do not silently overwrite BREERO authoritative state.
2. Record the discrepancy as reconciliation or operational exception state.
3. Preserve external evidence/reference IDs.
4. Resolve through an authorized command with reason/audit.
5. Use compensating financial journal entries rather than editing historical entries.

## Change control

Any change to this matrix requires an ADR or equivalent reviewed architecture change that states:

- old authority;
- new authority;
- migration/reconciliation plan;
- security and classification impact;
- rollback plan;
- affected API/event/webhook contracts;
- evidence required before activation.