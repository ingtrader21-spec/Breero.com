# Data classification and handling baseline

Regenerated for source baseline `ee79c3cb0bd667c3456dd20521563017b7d2d246`. This is handling
policy and source-boundary evidence, not legal advice or production-retention certification.

| Class | Examples | Required handling |
|---|---|---|
| PUBLIC | Service catalog, approved public provider profile, published reviews | Integrity controls; publish/cache only approved fields |
| INTERNAL | Operational reason codes, non-sensitive configuration, aggregate KPIs | Authenticated workforce access; do not publish by default |
| CONFIDENTIAL | Customer/provider contact data, addresses, conversations, quotes, schedules, support cases | Tenant/record authorization, encryption, audited access, minimized telemetry |
| RESTRICTED | Credentials/tokens, tax IDs, background/license/insurance evidence, job evidence/signatures, payment/payout/fraud records | Least privilege, strong audit, secret/document isolation, no raw telemetry, explicit retention/legal hold |

## Store and flow rules

BREERO PostgreSQL/PostGIS is marketplace transactional authority. Redis is not a
system of record. OpenBao owns secrets/PKI. Klyrow/Telnexa receive only data needed
for authorized delivery. Middleware receives governed minimum event payloads and
Odoo remains a projection. Analytics must use projections/reporting stores rather
than mutation paths.

## Current implementation boundary

The source inventory records 17 backend domain packages,
4 worker tasks and 201 unique logical
API operations across the inventoried profiles. Those counts do not prove complete
retention, export, deletion, legal hold, secure-document, messaging/support, or
financial certification. Those remain owned by their M00–M30 gates.

## Never log

Passwords, access/refresh/reset tokens, API keys, webhook secrets, OpenBao material,
SMTP/SMS credentials, raw payment data, full private document contents, and unrestricted
trust/safety notes must not enter logs, traces, metrics or analytics labels.

## Retention rule

Do not invent retention durations. Automated deletion/retention remains disabled
until approved product/legal policy, evidence preservation, financial/audit constraints,
and restore/reconciliation behavior are explicitly certified.
