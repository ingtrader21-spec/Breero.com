# BREERO Odoo Campaign CRM — Odoo 19 Platform and Review Gates

## Status

Binding companion to `ODOO_CAMPAIGN_CRM_IMPLEMENTATION.md`.

The implementation target is **Odoo 19**. Every implementation PR must record the exact Odoo edition, build/image digest, Python/PostgreSQL versions, installed dependency modules and addon path used for validation. Do not claim Odoo 19 compatibility from source inspection alone.

This document does not install, upgrade or activate an Odoo module.

## Authority boundary

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

Odoo 19 owns only its campaign CRM workflow, activities, agent/supervisor workspace, approved mailbox projection, integration inbox/outbox, mappings and local operational reporting.

Odoo must not connect with write authority directly to BREERO business tables. Any marketplace change uses an authenticated, allowlisted BREERO command/API and returns through the normal authorization, record-policy, capability, idempotency, audit and outbox path.

## Odoo 19 compatibility rules

Every addon must:

- use Odoo 19-supported manifest, model, field, view, action, menu, security and scheduled-action APIs;
- declare exact dependencies in `__manifest__.py` rather than relying on transitive installation;
- avoid deprecated XML/view syntax and private framework APIs;
- avoid monkey patches unless separately reviewed with upgrade and rollback evidence;
- keep module names, XML IDs, model names and external IDs stable after release;
- include migration hooks/scripts for schema or semantic changes;
- install into a clean disposable Odoo 19 database and upgrade from the current supported module version;
- fail with a clear configuration error when a required dependency or external endpoint is absent.

Optional Enterprise-only modules such as Helpdesk or Documents must not become mandatory unless the selected Odoo 19 edition and license are explicitly recorded and approved.

## Multi-company and tenant isolation

`company_id` alone is not sufficient when BREERO tenant and campaign boundaries are narrower than Odoo company boundaries.

For every campaign-scoped model:

```text
model access (ir.model.access.csv)
AND record rule (ir.rule)
AND active tenant/company context
AND active campaign membership
AND role-specific record scope
= access
```

Rules:

- no global read rule for campaign agents;
- no generic CRM-team membership as a substitute for campaign membership;
- no cross-company access through `allowed_company_ids` without matching BREERO tenant/campaign authority;
- no `sudo()` in user-facing business paths unless the exact elevation is narrowly scoped, justified and audited;
- integration service accounts use dedicated groups and cannot inherit ordinary agent/admin access;
- inactive/removed memberships and disabled users/mailboxes fail closed immediately;
- exports, attachments, chatter, search, name lookup, activities and reporting must obey the same record scope as primary forms/lists.

## Safe-mode and outbound channel posture

Default configuration in every environment until separately approved:

```text
outbound_email=false
outbound_sms=false
telephony_write=false
automatic_workflow_execution=false
marketing_send=false
```

Odoo fields such as `email_enabled`, `sms_enabled`, `phone_enabled`, `outbound_enabled` and per-agent send permissions are necessary but not sufficient. Effective send authorization requires:

```text
system channel enabled
AND campaign channel enabled
AND active campaign membership
AND mailbox identity active
AND recipient/contact access authorized
AND purpose allowed
AND consent present where required
AND suppression/do-not-contact clear
AND safe_mode policy permits
AND daily/rate limits permit
AND middleware/provider configured
```

Missing, unreadable or conflicting state fails closed.

## Mail safety

Odoo `mail.thread`, `mail.mail`, templates, activities and automated actions can generate outbound messages indirectly. Before enabling any module in staging or production:

- inventory every mail-producing model, template, automated action, scheduled action and server action;
- disable or redirect all non-approved outbound paths;
- use approved safe recipients/sink configuration in staging;
- prevent catchall, bounce, alias or reply routing from crossing tenants/campaigns;
- store no raw SMTP/API credential in business records, chatter, logs or exported configuration;
- require attachment size/type policy and malware/quarantine handling before delivery;
- verify duplicate, retry, bounce, suppression and terminal-failure behavior through the integration inbox/outbox;
- audit supervised mailbox access and every send attempt/result.

An installed mailbox module is not send approval.

## Integration authentication

Machine traffic between Odoo, middleware and BREERO must use approved service identity and transport policy.

Required controls:

```text
registered client/service identity
short-lived credentials or approved signed request
canonical audience/issuer where OAuth is used
tenant and campaign allowlist
request timestamp/replay protection where signed
idempotency key and request hash
correlation ID
request-size/content-type limits
schema/event/command allowlist
secret redaction
```

Odoo integration endpoints must durably persist accepted events before asynchronous projection work. They must reject unknown tenant, campaign, event type, aggregate mapping, schema version and service identity.

## Data classification and retention

- precise customer contact/location data remains `NONE`, `MASKED` or `AUTHORIZED` according to authoritative contact-access state;
- raw credential, identity, payment and job-evidence documents stay outside Odoo by default;
- projected fields require an allowlist, purpose, classification, retention and deletion behavior;
- chatter and notes must not become an unrestricted PII dumping ground;
- payload storage in integration inbox/outbox must be minimized/redacted and access-controlled;
- deletion/suppression requests must define what is removed, anonymized or retained for legal/audit reasons;
- backups and exports inherit the highest classification of their contents.

## Module delivery sequence

```text
1. core tenant/campaign models
2. security groups, ACLs and record rules
3. integration mappings/inbox/outbox with sends disabled
4. projection sync and reconciliation
5. agent workspace
6. mailbox UI with all outbound channels disabled
7. supervisor workspace
8. compliance/suppression controls
9. reporting
10. provider recruitment projection
11. separately reviewed channel activation, one channel/purpose at a time
```

No dependent module should be deployed before its security and data migrations are accepted.

## Upgrade and rollback evidence

Every implementation PR must provide, where applicable:

```text
BASE_ODOO_VERSION
FINAL_ODOO_VERSION
IMAGE_DIGEST
ADDONS_CHANGED
MODULE_VERSION_BEFORE
MODULE_VERSION_AFTER
DEPENDENCIES
CLEAN_INSTALL=PASS/FAIL
UPGRADE_FROM_SUPPORTED_VERSION=PASS/FAIL
MIGRATION_RESULT
ACL_TESTS
RECORD_RULE_TESTS
MULTI_COMPANY_TESTS
NEGATIVE_AUTH_TESTS
INTEGRATION_TESTS
MAIL_SAFETY_TESTS
STAGING_STATUS
ROLLBACK_OR_FORWARD_FIX_BOUNDARY
EXTERNAL_SENDS_ENABLED=false
UNRESOLVED_RISKS
```

Database backup/restore evidence is required before a production module upgrade. Do not use production as the first upgrade test. An uninstall is not assumed safe when it would drop operational history; document archival/forward-fix behavior instead.

## Mandatory Odoo 19 tests

At minimum:

```text
clean install
upgrade from supported prior module version
agent A denied agent B private lead/mailbox
agent denied other campaign and tenant
supervisor denied unrelated campaign/tenant
removed membership denied immediately
support denied unauthorized full PII
finance denied unrelated CRM/mailbox
agent/supervisor denied raw secrets
record-rule enforcement through forms, lists, search, chatter, activities, attachments, exports and reports
sudo/elevation paths reviewed and tested
invalid service identity/tenant/campaign/event denied
duplicate and out-of-order integration event
stale external version and mapping conflict
middleware/provider outage and retry/terminal state
disabled mailbox/channel cannot send
do-not-contact/suppression blocks prohibited purpose
staging safe-recipient containment
```

## Activation gate

CRM read/projection functionality may be reviewed separately from outbound channels.

Each outbound channel/purpose requires a separate activation change naming:

```text
channel and purpose
campaign/tenant scope
exact release/module versions
middleware/provider configuration
consent/suppression policy
safe-recipient/canary plan
rate/daily limits
monitoring and alerting
abort thresholds
rollback/disable procedure
authorizing owner
```

Until that change is independently approved and verified:

```text
EXTERNAL_SENDS_ENABLED=false
TELEPHONY_WRITE_ENABLED=false
AUTOMATIC_WORKFLOW_EXECUTION=false
```

Documentation completion, module installation or successful staging projection does not activate external communication.
