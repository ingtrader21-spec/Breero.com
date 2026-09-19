# BREERO Odoo 19 Campaign CRM — Production Implementation Contract

## Status

Binding implementation contract for the BREERO campaign CRM projection and operational workspace.

This document replaces the earlier parallel-addon mission layout. The implementation must extend the Odoo 19 addon and integration contract already present in the accepted BREERO repository.

```text
ODOO_TARGET=19
EXISTING_ADDON=odoo-addons/breero_crm
EXISTING_ADDON_VERSION=19.0.1.0.0
EXISTING_INBOUND_MODEL=breero.sync.event
PARALLEL_REPLACEMENT_TREE=FORBIDDEN
EXTERNAL_SENDS_ENABLED=false
TELEPHONY_WRITE_ENABLED=false
AUTOMATIC_WORKFLOW_EXECUTION=false
PRODUCTION_READY=NO
```

Companion platform, upgrade, mail-safety, multi-company, and activation requirements are in `ODOO_CAMPAIGN_CRM_PLATFORM_AND_REVIEW_GATES.md`.

# 1. Objective

Extend the existing Odoo codebase into a modern campaign CRM for:

```text
campaign setup
campaign-scoped agents and supervisors
lead/customer workspace
call dispositions and after-call workflow
callback scheduling
appointments and reminders
activities and notes
inbound/outbound mailbox projection
approved email/SMS/telephony requests through middleware
operational queues and escalations
quality/compliance controls
reporting
BREERO projection and command links
```

Odoo is a projection and operational workspace. It is not the authoritative marketplace database.

# 2. Existing module compatibility is mandatory

The accepted repository already contains:

```text
odoo-addons/breero_crm/
├── __manifest__.py            # Odoo 19 module, version 19.0.1.0.0
├── models/breero_sync_event.py
├── models/breero_crm_case.py
├── models/crm_lead.py
├── models/res_partner.py
├── security/
├── data/
├── views/
└── tests/
```

BREERO API integration already delivers to the model contract:

```text
breero.sync.event
```

Therefore implementation must:

- extend `odoo-addons/breero_crm` in place for the first production increment;
- preserve the module technical name `breero_crm`;
- preserve existing model names, external IDs, mappings, views, security groups, scheduled jobs, and inbound delivery behavior unless a reviewed migration explicitly changes them;
- upgrade the manifest version according to Odoo 19 versioning policy;
- use migration scripts/hooks for schema or semantic changes;
- prove clean install and upgrade from `19.0.1.0.0`;
- preserve rollback/forward-fix compatibility with the currently accepted BREERO API delivery contract.

## 2.1 Future module split

A later split into dependent addons is allowed only through a staged compatibility plan:

```text
1. new addon depends on breero_crm
2. current breero.sync.event remains available
3. data/XML IDs are migrated without duplication
4. producer and consumer compatibility is tested
5. old and new versions can coexist during rollout if required
6. all producers are switched and verified
7. removal happens only in a separate reviewed release
```

Do not create a disconnected `addons/` tree that bypasses the existing deployment artifact.

# 3. System-of-record boundary

BREERO PostgreSQL/PostGIS remains authoritative for:

```text
ProjectRequest
matching
Opportunity
LeadConnection
Conversation authority
Quote
Booking
Job
Review
Dispute
provider eligibility
capability state
payment/refund/earning/payout state
```

Odoo owns only its campaign CRM workflow, projections, activities, notes, agent/supervisor assignments, approved mailbox projection, integration inbox/outbox, mappings, and local operational reporting.

Odoo never writes directly to BREERO business tables. A requested marketplace mutation uses an authenticated allowlisted BREERO command/API and returns through normal BREERO authorization, record policy, capability, idempotency, audit, and outbox handling.

# 4. Tenant, company, and campaign authority

Every campaign-scoped business record carries first-class scope:

```text
company_id
breero_tenant_id or authoritative tenant mapping
campaign_id
```

Where legal entities differ from Odoo companies, persist the authoritative external legal-entity identifier or mapping as well.

Scope is not inferred solely from payload text, a CRM team, current UI company, user context, or a related lead after the fact.

# 5. Core Odoo models

Extend the existing addon with reviewed models or extensions for:

```text
breero.crm.campaign
breero.crm.campaign.membership
breero.crm.membership.history
breero.crm.mailbox
breero.crm.disposition
breero.crm.callback
breero.crm.appointment
breero.crm.integration.mapping
breero.crm.integration.inbox
breero.crm.integration.outbox
breero.crm.delivery
breero.crm.operational.exception
breero.crm.access.audit
```

Technical names may be adjusted to fit existing accepted names, but ownership and constraints below are binding.

# 6. Campaign membership is a security authority

A campaign membership grants campaign-scoped role and assignment authority. Duplicate authoritative memberships are forbidden.

Required fields:

```text
campaign_id
user_id
company_id
tenant mapping
role
active
started_at
ended_at
created_by
updated_by
```

## 6.1 Uniqueness rule

Use one authoritative membership row per campaign and user:

```text
UNIQUE (campaign_id, user_id)
```

Activation, deactivation, role changes, and assignment changes update that row through audited commands.

Historical periods belong in an append-only membership-history/audit model, not duplicate current membership rows.

This prevents imports, retries, or concurrent administration from creating two rows where one is inactive and another silently keeps access active.

## 6.2 Immediate revocation

Removing or deactivating a membership must immediately deny:

```text
campaign leads/cases
mailboxes and messages
activities/callbacks/appointments
attachments and chatter
search/name lookup
exports and reports
queues and dashboards
integration retry/replay actions
```

Cache/session behavior must not preserve access beyond the approved revocation window.

# 7. Roles and separation of duty

Initial campaign roles:

```text
agent
closer
supervisor
quality
support
campaign_admin
integration_service
```

Role name alone is insufficient. Access requires active company/tenant/campaign membership and record scope.

Representative boundaries:

- agents see only assigned or approved shared-queue records in their campaign;
- closers see only campaigns and queues assigned to them;
- supervisors see supervised campaign scope, not every tenant/company;
- quality sees recordings/evidence only under approved QA policy;
- support sees minimum fields required for an assigned case;
- campaign admins cannot read raw integration secrets;
- integration service accounts cannot inherit interactive agent/admin access;
- finance/trust/marketplace authority is not implied by CRM roles.

# 8. Security implementation

For every model, implement both:

```text
ir.model.access.csv
AND ir.rule record rules
```

Access decision:

```text
model permission
AND active company/tenant context
AND active campaign membership
AND role-specific record scope
= ALLOW
```

Rules cover forms, lists, kanban, search, name lookup, chatter, activities, attachments, exports, reports, dashboards, scheduled actions, and RPC/API access.

Avoid broad `sudo()`. Any elevation is narrowly scoped, documented, audited, and tested.

# 9. CRM lead/case projection

Extend current `crm.lead`, `res.partner`, and `breero.crm.case` projection behavior rather than creating duplicate customer/lead universes.

Projection records include stable external identity and version fields:

```text
breero_tenant_id
campaign_id
source_system
external_aggregate_type
external_aggregate_id
external_version
last_event_id
last_synced_at
contact_access_state
projection_status
```

Updates are idempotent and reject/park stale external versions according to policy.

Odoo stage changes are operational workflow only. They do not become authoritative BREERO marketplace state.

# 10. Agent workspace

Provide a clean Odoo 19 workspace with:

```text
My queue
Today’s callbacks
Appointments
Open conversations
Needs disposition
Escalations
Recently contacted
Customer/case context
Approved contact channels
Notes and activities
```

The workspace must remain usable with keyboard navigation and standard Odoo accessibility behavior. It must not expose fields outside the user’s scope.

# 11. After-call disposition workflow

After a completed telephony event, create an after-call disposition wizard/activity when policy requires it.

Required disposition data:

```text
campaign
lead/case
agent
call external ID
outcome
reason
notes
next action
callback requested
callback time/timezone
appointment requested
consent/suppression changes where authorized
```

Rules:

- the wizard never changes authoritative BREERO marketplace state directly;
- incomplete required dispositions remain visible in the agent/supervisor queue;
- duplicate telephony callbacks do not create duplicate disposition work;
- write access is limited to the call’s assigned campaign/agent or authorized supervisor;
- QA/supervisor corrections are audited, not silently overwritten.

# 12. Callback and appointment scheduling

When a customer requests a callback or appointment:

```text
create/update campaign-scoped callback or appointment
create Odoo activity for assigned agent/queue
record customer timezone and normalized UTC time
link source call/message/case
emit approved notification intent only when channel policy permits
```

Reminder policy may include:

```text
30 minutes before → agent reminder
15 minutes before → preparation reminder and approved customer/agent notification
```

The exact timings are configurable per campaign. Missing channel authorization fails closed; the internal activity still remains visible.

Concurrent edits use version/conflict handling so two agents do not silently overwrite the same callback.

# 13. Mailbox and communication projection

Mailbox records are campaign and company scoped. They contain approved identities and routing metadata, not raw provider credentials.

Required controls:

```text
active mailbox
campaign membership
company/tenant scope
purpose
recipient/contact authorization
consent where required
suppression/do-not-contact
safe mode
per-agent permission
daily/rate limits
middleware/provider readiness
```

All must pass before a send request can be emitted.

Odoo templates, `mail.thread`, `mail.mail`, automated actions, scheduled actions, aliases, catchall, bounce, and reply routing must be inventoried so no indirect path bypasses the approved middleware/outbox.

# 14. Integration inbox

Extend the existing `breero.sync.event` contract or stage a compatible successor. Accepted integration records must persist validated first-class scope before they enter campaign processing.

Required fields/relations include:

```text
provider/source
external_event_id
event_type
schema_version
request/body hash
authentication result
company_id
breero_tenant_id or tenant mapping
campaign_id when campaign-scoped
legal_entity mapping where applicable
aggregate type/id/version
status
attempt_count
claimed_by
claim_token
lease_expires_at
next_attempt_at
received_at
processed_at
correlation_id
last_error_code
approved minimized/redacted payload
```

## 14.1 Scope resolution before acceptance

Target inbound flow after the compatibility rollout:

```text
verify service identity/signature
parse the minimal envelope
validate tenant/company/campaign identifiers
resolve active mappings
persist accepted row with first-class scope
acknowledge
process asynchronously
```

This ordering is not activated against the current BREERO producer until the following staged acknowledgment rollout completes.

## 14.2 Acknowledgment compatibility rollout

### Stage A — preserve the deployed synchronous contract

- Extend the existing `odoo-addons/breero_crm` module and preserve the `breero.sync.event` model and `process_breero_event` method.
- Preserve the current producer contract in `apps/api/app/integrations/odoo.py`: successful delivery returns a truthy target `odoo_record_id` (and `odoo_model` where available) only after the target projection exists.
- Do not return an inbox record ID as `odoo_record_id`; that would falsely mark an inbox row as the delivered business projection.
- Stage A remains the rollback-compatible behavior until both sides support Stage B.

### Stage B — separately review queued acknowledgment support

Stage B also requires a versioned producer request envelope before any queued acknowledgment rollout. BREERO publishes a business event to Middleware with `schema_version`, `event_id`, `event_type`, `tenant_id`, `legal_entity_id`, `campaign_id` when campaign-scoped, `correlation_id`, `occurred_at`, and `data`. Middleware validates the producer's authenticated tenant grant, derives the authorized Odoo company/campaign mapping from its registry, and sends the mapped versioned envelope to Odoo. Raw payload text and Odoo request context are not scope authority.

Deploy receiver schema validation first, then the Middleware mapping, then the BREERO producer contract in separately reviewed changes. Existing unscoped Stage A events cannot enter campaign processing: retain them in restricted quarantine until an authorized mapping/replay supplies validated scope. Never infer global scope for backward compatibility. Require matching producer/consumer contract tests, rejection of missing/conflicting scope, duplicate-event tests, and a staged replay receipt before switching acknowledgments. Rollback restores the previous producer/receiver protocol without replaying scoped records through an unscoped path.


Introduce a separately reviewed producer contract that can explicitly accept:

```json
{
  "accepted": true,
  "queued": true,
  "inbox_id": "provider-scoped-inbox-id",
  "target_record_id": null
}
```

The BREERO producer must validate this shape deliberately; absence of a target record must remain `ODOO_INVALID_ACK` for legacy or ambiguous responses. A queued acknowledgment records durable acceptance only and must never be stored as a delivered projection. Delivery state distinguishes at least `QUEUED`, `PROJECTED`, `REJECTED`, `FAILED_RETRYABLE`, and `FAILED_TERMINAL`, with correlation and reconciliation from inbox ID to the eventual target model/record.

Mandatory compatibility tests cover legacy synchronous success, explicit queued acceptance, malformed/ambiguous acknowledgment rejection, queued-not-delivered accounting, later projection correlation, duplicate delivery, retry, and rollback to the Stage A producer/consumer pair.

### Stage C — staging-verified activation

Activate asynchronous acknowledgment only after the separately reviewed BREERO producer and Odoo consumer versions are deployed together in isolated staging. Prove synchronous rollback compatibility, queued/projected reconciliation, duplicate safety, outage recovery, and no false delivered projection before activation. Production activation requires an explicit reviewed change and must retain Stage A rollback artifacts throughout the transition.

An unknown or conflicting tenant/company/campaign mapping is denied or placed in a dedicated restricted quarantine state. It is not accepted as a globally visible unscoped campaign event.

Record rules use the first-class scope columns. They do not parse an opaque payload to decide access.

Unique provider/event identity and claim-token-safe worker processing prevent duplicate business effects.

# 15. Integration outbox and deliveries

Outbox records also persist:

```text
company_id
breero_tenant_id or tenant mapping
campaign_id when campaign-scoped
purpose
destination/event or command type
aggregate identity/version
idempotency key
correlation/causation
status/attempts
claim ownership/lease
next attempt
terminal error
```

The outbox may request only allowlisted BREERO/middleware operations. It does not store raw secrets and does not create an alternative authoritative marketplace command path.

Every claim receives a fresh token; stale workers cannot finalize a newer claim. Disabled external channels park safely without false delivery.

# 16. Integration mappings

Mappings are explicit and versioned:

```text
BREERO tenant ↔ Odoo company
BREERO campaign ↔ Odoo campaign
BREERO user/agent ↔ res.users
BREERO aggregate ↔ Odoo projection
provider/mailbox identity ↔ approved campaign channel
```

Ambiguous mappings fail closed. Administrative changes require permission, reason, audit, and reconciliation.

# 17. Operational exceptions and reconciliation

Create visible exceptions for:

```text
unknown tenant/campaign
stale projection version
mapping conflict
duplicate conflict
terminal inbox/outbox failure
mailbox disabled
suppression/consent block
provider outage
callback/appointment ownership conflict
record-rule inconsistency
```

Authorized operators may acknowledge, assign, note, retry/replay where safe, and resolve with reason. Retry/replay retains tenant/campaign scope and idempotency.

Scheduled reconciliation compares BREERO projection/version state with Odoo mappings without making Odoo authoritative.

# 18. Data classification

Contact data uses explicit access state:

```text
NONE
MASKED
AUTHORIZED
```

Precise phone, email, address, access instructions, recordings, attachments, credentials, and financial information require approved purpose and field-level policy.

Raw credential, payment, identity, and job-evidence documents remain outside Odoo by default. Chatter, notes, payloads, logs, exports, and reports must not become unrestricted PII storage.

# 19. External communication defaults

Until a separate activation change is reviewed and approved:

```text
outbound_email=false
outbound_sms=false
telephony_write=false
automatic_workflow_execution=false
marketing_send=false
```

An installed module, active mailbox record, template, campaign flag, or successful staging projection does not activate a channel.

Each channel/purpose activation identifies exact module versions, campaign/tenant scope, middleware/provider configuration, consent/suppression policy, canary recipients, limits, monitoring, abort thresholds, disable procedure, and authorizing owner.

# 20. Reporting

Campaign reporting may include:

```text
queue age
contact attempts
callback SLA
appointment adherence
disposition completion
agent/supervisor workload
inbox/outbox health
terminal failures
suppression blocks
projection lag
```

Reports obey the same company/tenant/campaign record rules as operational records and do not expose unrestricted PII.

# 21. Upgrade and migration sequence

Implementation order:

```text
1. extend existing breero_crm manifest/models
2. add migrations and stable external IDs
3. add membership uniqueness/history
4. add company/tenant/campaign first-class scope
5. update ACLs and record rules
6. upgrade existing breero.sync.event compatibility
7. add inbox/outbox lease/idempotency behavior
8. add agent/supervisor workspace
9. add disposition/callback/appointment workflow
10. add mailbox UI with all outbound channels disabled
11. add reporting and reconciliation
12. stage in isolated Odoo 19
13. separately review each channel activation
```

Before upgrade:

- backup the Odoo database and filestore;
- test clean install and upgrade from `19.0.1.0.0`;
- inventory current XML IDs/models/cron/actions/security;
- prove existing BREERO deliveries still resolve `breero.sync.event`;
- document rollback or forward-fix boundary.

# 22. Mandatory tests

At minimum:

```text
clean Odoo 19 install
upgrade from breero_crm 19.0.1.0.0
existing breero.sync.event delivery compatibility
one membership row per campaign/user enforced
concurrent duplicate membership rejected
membership deactivation immediately revokes access
agent denied other agent private lead/mailbox
agent denied other campaign and tenant
supervisor denied unrelated campaign/tenant
record rules cover form/list/search/chatter/activity/attachment/export/report
unknown tenant/company/campaign event denied or restricted quarantine
accepted inbox row always has validated first-class scope
inbox/outbox record rules use scope columns
integration duplicate event has one projection effect
stale projection version parked
stale claim cannot finalize newer claim
invalid service identity denied
disabled mailbox/channel cannot send
suppression/do-not-contact blocks prohibited purpose
staging safe-recipient containment
automated action/template cannot bypass middleware policy
callback/appointment timezone and duplicate handling
reminder scheduling without unauthorized send
backup/restore/upgrade smoke
```

# 23. Pull-request evidence

Every implementation PR reports:

```text
BASE_MAIN_SHA
FINAL_SHA
ODOO_EDITION_AND_BUILD
ODOO_IMAGE_DIGEST
MODULE_VERSION_BEFORE
MODULE_VERSION_AFTER
EXISTING_MODELS_AND_XML_IDS_PRESERVED_OR_MIGRATED
CLEAN_INSTALL
UPGRADE_RESULT
DATABASE_AND_FILESTORE_BACKUP_EVIDENCE
ACL_TESTS
RECORD_RULE_TESTS
MEMBERSHIP_UNIQUENESS_TESTS
TENANT_CAMPAIGN_SCOPE_TESTS
INTEGRATION_COMPATIBILITY_TESTS
MAIL_SAFETY_TESTS
STAGING_STATUS
ROLLBACK_OR_FORWARD_FIX_BOUNDARY
EXTERNAL_SENDS_ENABLED=false
TELEPHONY_WRITE_ENABLED=false
AUTOMATIC_WORKFLOW_EXECUTION=false
UNRESOLVED_RISKS
```

Documentation completion alone does not install, upgrade, deploy, send, call, or activate anything.
