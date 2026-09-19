# BREERO Marketplace V2 — Data Classification Policy

## Status

Binding policy for classification, storage, logging, projection, retention, backup and export of BREERO data.

This policy applies to application code, PostgreSQL/PostGIS, Redis, object storage, logs, traces, analytics, Odoo, Codestra/Kong/middleware, n8n, Klyrow, Telnexa and every external provider.

## Classification levels

```text
PUBLIC
INTERNAL
CONFIDENTIAL
RESTRICTED
HIGHLY_RESTRICTED
```

A dataset inherits the **highest classification of any field it contains** unless an approved redaction/projection explicitly removes the higher-class data.

## Handling matrix

| Class | Typical visibility | Storage | Logging | Projection | Encryption | Export |
|---|---|---|---|---|---|---|
| PUBLIC | Anyone | Approved public/private systems | Allowed if useful | Allowed | Standard transport/storage controls | Allowed |
| INTERNAL | BREERO workforce/service identities with business need | Approved internal systems | Safe metadata only | Approved internal processors only | In transit; at rest per platform baseline | Permissioned |
| CONFIDENTIAL | Authorized customer/provider/worker/staff scopes | BREERO authoritative stores and approved processors | Avoid full values; identifiers only where needed | Only minimum approved projection | In transit + at rest | Explicit permission + audit |
| RESTRICTED | Narrow role/record scope | Approved authoritative/private storage only | Redacted/hashed/tokenized only | Status/summary only unless contract explicitly permits | Strong in transit + at rest; key access controlled | Dedicated permission + purpose + audit |
| HIGHLY_RESTRICTED | Exceptional least-privilege access | Specifically approved secure stores/processors | Never log raw values | Never project by default | Strong encryption, strict secret/key separation | Exceptional permission, reason, short-lived delivery, audit |

## Data examples

### PUBLIC

Examples:

- public service catalog text;
- public service descriptions;
- public provider marketing profile fields explicitly approved for publication;
- public help/policy content;
- public capability projection that contains no secrets/internal state;
- published service-area statements intended for customers.

### INTERNAL

Examples:

- internal feature names;
- non-sensitive operational metrics;
- deployment metadata such as Git SHA/image digest;
- internal queue names;
- non-sensitive configuration identifiers;
- internal runbook references;
- provider integration status without credentials.

### CONFIDENTIAL

Examples:

- customer account/profile information;
- ProjectRequest details that do not contain higher-class fields;
- customer address/property information;
- provider membership/workforce data;
- quotes and conversations;
- booking/job status and notes;
- non-sensitive provider documents already approved for that workflow;
- support notes;
- operational exception details;
- notification history.

### RESTRICTED

Examples:

- government/business identifiers where legally or operationally sensitive;
- provider licensing/insurance evidence;
- worker identity/verification documents;
- precise customer contact details exposed to providers/workers;
- dispute evidence;
- payout destination metadata;
- payment/refund/payout transaction details;
- signed contracts or identity-bearing documents;
- sensitive location/access instructions;
- detailed security/audit metadata.

### HIGHLY_RESTRICTED

Examples:

- passwords and password-equivalent secrets;
- private keys;
- API secrets;
- Keycloak/OIDC client secrets;
- database credentials;
- Redis credentials;
- Odoo/Codestra/n8n/Klyrow/Telnexa credentials;
- object-storage credentials;
- payment/payout provider secrets;
- raw authorization headers, cookies or bearer tokens;
- full bank account/routing details if ever processed;
- card data BREERO is not explicitly approved to store;
- raw identity verification data whose exposure creates major identity-theft risk;
- malware samples/quarantined executable content.

## System-specific rules

### PostgreSQL/PostGIS

May store authoritative PUBLIC through HIGHLY_RESTRICTED business data only when the schema, permissions, encryption posture and retention policy explicitly support it.

Runtime roles must be least privilege. HIGHLY_RESTRICTED values should be minimized, tokenized/encrypted at field level where justified, and avoided entirely when a provider token/reference can be authoritative instead.

### Redis

Redis is not an authoritative store.

Allowed:

- cache;
- rate-limit counters;
- queue metadata;
- temporary locks;
- short-lived derived state;
- circuit-breaker state.

Do not place HIGHLY_RESTRICTED raw data in Redis unless an approved design specifically requires it and defines TTL, encryption/network isolation and incident handling. Prefer opaque IDs/references.

### Object storage

All non-public uploaded objects are private by default.

RESTRICTED/HIGHLY_RESTRICTED objects require:

- private ACL/container;
- tenant/resource authorization;
- malware scanning/quarantine;
- encryption at rest;
- short-lived signed access;
- retention/deletion policy;
- no permanent public URL.

### Logs, traces and metrics

Never log:

```text
passwords
bearer tokens
Authorization headers
session cookies
private keys
API secrets
database credentials
full bank details
full card data
raw provider credentials
malware content
```

CONFIDENTIAL/RESTRICTED data should normally be represented by opaque identifiers, hashes, counts, state names or redacted values.

Correlation IDs are allowed. They must not encode PII.

### Audit

Audit may contain CONFIDENTIAL and selected RESTRICTED metadata needed for security/accountability, but should record safe identifiers/hashes rather than raw sensitive payloads.

Audit must never copy HIGHLY_RESTRICTED secrets.

### Odoo

Odoo is a CRM projection/workspace, not marketplace authority.

Allowed by default:

- CRM identifiers;
- customer/provider display/contact data required for approved CRM workflow;
- ProjectRequest/booking/job summaries;
- workflow status/stage;
- approved notes/activities;
- projection IDs and timestamps.

Not allowed by default:

- payment credentials;
- payout credentials;
- raw provider secrets;
- raw security tokens;
- HIGHLY_RESTRICTED verification material;
- full audit/security evidence;
- data explicitly marked “never project.”

### Codestra/Kong/middleware

May transport the minimum payload needed for an approved integration. It must not become a secondary data lake.

Avoid durable storage of RESTRICTED payloads unless needed for reliable delivery/reconciliation and explicitly governed by retention.

Never transport raw HIGHLY_RESTRICTED secrets as business-event payload fields.

### n8n

n8n receives only the minimum fields needed by an allowlisted workflow.

Do not use n8n as a general database mirror or long-term store of marketplace/private data.

HIGHLY_RESTRICTED values are prohibited in workflow variables/execution history unless an explicit security review authorizes the exact use.

### Klyrow / email

Email content should contain the minimum customer/provider data necessary for the transaction. Avoid RESTRICTED/HIGHLY_RESTRICTED content. Prefer secure portal links for sensitive details.

### Telnexa / SMS

SMS is unsuitable for HIGHLY_RESTRICTED content and should avoid RESTRICTED data. Use short, purpose-limited transactional content and secure portal links.

### Analytics

Analytics events must be schema-reviewed and classification-reviewed.

Do not send HIGHLY_RESTRICTED data. RESTRICTED data requires explicit business/security approval and minimization; prefer stable pseudonymous identifiers.

## Projection rules

Before projecting data to another system, define:

```text
source_field
classification
purpose
destination
transformation/redaction
retention
owner
```

A projection that is not documented and approved is denied by default for RESTRICTED/HIGHLY_RESTRICTED fields.

## Export rules

### PUBLIC

No special export restriction beyond normal integrity controls.

### INTERNAL

Requires authenticated workforce/service access appropriate to purpose.

### CONFIDENTIAL

Requires explicit export permission and audit for bulk exports.

### RESTRICTED

Requires dedicated permission, reason/purpose, rate limiting, short-lived secure delivery and audit. Watermarking should be used where appropriate.

### HIGHLY_RESTRICTED

Bulk export is denied by default. Any exception requires explicit security/financial/legal approval as appropriate, exact-field minimization, short-lived delivery and complete audit.

## Backup rules

Backups inherit the highest data classification they contain.

Production backups must be:

- encrypted;
- access-controlled separately from normal runtime credentials;
- stored off-host/off-service where required;
- retention-governed;
- checksum/restore-tested;
- deleted/expired according to approved policy.

## Retention and deletion

Classification does not by itself determine retention duration. `06_DATA_FILE_RETENTION_POLICY.md` and the approved retention matrix define duration/legal-hold behavior.

Deletion/anonymization workflows must also clean approved projections and object storage while preserving immutable audit/financial evidence that must legally or operationally remain.

## CI/review enforcement

Schema/event/API changes that add sensitive fields must answer:

```text
What is the classification?
Where is it authoritative?
Who can read it?
Can it be logged?
Can it be projected?
How long is it retained?
Can it be exported?
How is it deleted/anonymized?
```

A new RESTRICTED/HIGHLY_RESTRICTED field without those answers is not production-ready.