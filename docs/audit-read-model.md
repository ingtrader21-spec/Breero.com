# Audit read model, security activity view, and retention contract

Status: implemented on `feature/audit-security-readmodel-20260925` (migration
`023_audit_read_model`). Read-only. No purge, archival, export, or external delivery.

## Source of record

`audit_logs` (PostgreSQL) remains the single audit store. Every domain keeps writing
`AuditLog` rows in the same transaction as its mutation (see
[`audit-log-matrix.md`](audit-log-matrix.md)). Other event-like tables were inventoried
and deliberately **not** merged into this view:

| Table | Why it is not part of the admin audit read model |
|---|---|
| `integration_events` | Transactional outbox; payloads can hold contact data and delivery tokens. Admin retries are audited as `integration.retry`. |
| `job_events` | Job state-machine history; job transitions of interest are already audited. |
| `payment_events` | Provider webhook ledger; payment-provider payloads. |
| `worker_location_events` | Location telemetry (PII). |
| `consent_events`, `privacy_requests.history` | Compliance evidence with its own access path; privacy requests are audited as `privacy_request.received`. |

## Stored fields (additive migration `023_audit_read_model`)

| Column | Source |
|---|---|
| `result` | `success` (default, and every pre-migration row) / `denied` / `failure`; check-constrained |
| `request_id`, `correlation_id` | Copied from the HTTP request context (`X-Request-ID` / `X-Correlation-ID`) by the `before_insert` listener |
| `source_ip_hash` | HMAC-SHA256 of the client address under a key derived from the server signing secret. The raw address is never stored. Hashed source values were already stored for privacy and consent records; this uses a keyed hash instead of a plain digest. |
| `vendor_id` | Provider-tenant context derived from `resource_type = 'vendor'` or `metadata.vendor_id` |

The same listener replaces values stored under secret-shaped keys (`password`, `secret`,
`token`, `api_key`, `authorization`, `cookie`, `private_key`) and bearer/JWT/API-key-shaped
string values with `[REDACTED]` before insert. Existing emitters did not need to change
for this.

Indexes: `(created_at DESC, id DESC)` for keyset paging, plus `(actor_id, created_at)`,
`(action varchar_pattern_ops, created_at)` for exact or prefix action filters,
`(resource_type, resource_id, created_at)`, and partial indexes on `correlation_id`,
non-success `result`, and `vendor_id`. Indexes are created inside the migration
transaction (not `CONCURRENTLY`). Check the table size before production rollout.

## API (`admin.audit.read`; only the `admin` and `superadmin` roles hold it)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/admin/audit/events` | Bounded search; summaries only |
| GET | `/api/v1/admin/audit/security-events` | Same filters, restricted to the security activity view |
| GET | `/api/v1/admin/audit/events/{event_id}` | Detail with allowlisted metadata |
| GET | `/api/v1/admin/audit/correlations/{correlation_id}` | Correlation trace, oldest first, capped at 200 |
| GET | `/api/v1/admin/audit/catalog` | Categories, limits, retention contract |

Filters: `occurred_from`/`occurred_to` (timezone required; default is the last 30 days;
maximum window 366 days), `actor_id`, `actor_type`, `action` or `action_prefix`,
`resource_type`, `resource_id`, `result`, `category` (event type), `correlation_id`,
`request_id`, `vendor_id`, `limit` (1–100, default 50), `cursor`.

Pagination uses an opaque keyset cursor on `(created_at, id)`. The cursor holds the
search window and a fingerprint of the filters. If a cursor is reused with different
filters, the API returns `400 AUDIT_CURSOR_INVALID`. Invalid or unbounded filters return
`422 AUDIT_FILTER_INVALID`. An unknown event returns `404 AUDIT_EVENT_NOT_FOUND`.

Metadata exposure uses an allowlist, not a denylist
(`app/domains/audit/redaction.py::METADATA_ALLOWLIST`). Free text (`note`, `reason`,
`previous_error`), contact details, nested objects, and anything that looks like a secret
or an e-mail address are withheld. The detail response reports how many keys were
withheld. The source fingerprint is truncated to 16 hex characters.

## Categories and the security activity view

Categories are derived from `action` at read time, so historical rows are classified
too: `access_denied`, `auth_lifecycle`, `access_change`, `privileged_admin` (geography
administration), `provider_decision`, `dispatch`, `finance`, `integration`, `privacy`, and
`domain` (everything else).

The security activity view contains every non-`success` row, the categories
`access_denied`, `auth_lifecycle`, `access_change`, `privileged_admin`,
`provider_decision`, and `integration`, and the actions `payout.approve` and
`payout.submit`.

## Emission added or normalized on this branch

| Path | Change |
|---|---|
| `require_roles` / `require_permissions` | Records `authz.denied` (`result=denied`) with the required roles or permissions. An audit failure never changes the 403. |
| `PUT /auth/access/users/{id}` | Role changes now emit `access.assignments.replace` with previous and new roles. The superadmin-grant refusal emits `authz.denied`. |
| `OutboxService.retry` | Adds `previous_status`, `previous_error_code`, `event_type`, `aggregate_type` |
| `FinanceService.approve_batch` | Adds status transition, total, currency, and count |
| Provider application decisions | Add `previous_status` and `vendor_id`, which sets the provider-tenant context |
| Dispatch assignment, geography admin, provisioning, payout submit | Already emitted. They now gain request context automatically. |

Known gaps (not implemented, no endpoint exists): user disable/reactivate
(`admin.user.disable`/`admin.user.reactivate` are already classified as `access_change`),
failed-login events, and dispatch reassignment (only `assignment.create` exists). Reads
of the audit API are not themselves audited.

## Retention contract

Served read-only at `/api/v1/admin/audit/catalog` (`retention`) and defined in
`app/domains/audit/catalog.py::RETENTION_POLICY`:

- audit rows are append-only by convention. No code path updates or deletes them.
- minimum retention: 2555 days (7 years) for all events, including security events.
  Compliance/legal must confirm this before it is relied on externally.
- `automated_purge: false`. This codebase contains no purge, archival, or deletion job.
  Any future purge must be a separately reviewed change with legal/compliance approval.
- legal hold is not implemented.

## Rollback

`023_audit_read_model` is additive. Downgrading drops the new columns and indexes, and
with them any request context captured after the upgrade. Prefer a forward fix. Older
application code can still write rows, because `result` has a server default and the
other new columns are nullable. However, older code pins `EXPECTED_SCHEMA_REVISION`, so
its readiness check reports the schema as `outdated` until the schema is downgraded.
