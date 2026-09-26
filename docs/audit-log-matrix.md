# Sensitive-action audit contract

Audit records are append-only. `actor_id` is the authenticated principal,
`resource_type/resource_id` identify the target, and metadata must never include credentials,
tokens, complete provider payloads, or secrets.

| Action | Actor | Target | Required metadata |
|---|---|---|---|
| `access.assignments.replace` | admin/super-admin | user | brand, previous/new roles |
| `authz.denied` (`result=denied`) | any authenticated principal | the principal | required roles/permissions, reason code |
| `assignment.create` / `assignment.release` | dispatcher/operations | job/assignment | vendor, worker, old/new state |
| `job.manual_transition` | operations/admin | job | from/to, reason |
| `quote.approve` / `quote.reject` | owning customer | quote | prior/new state, payment required |
| `refund.create` | operations/finance/admin | payment/refund | amount minor, currency, reason, provider reference |
| `compensation_plan.change` | finance/admin | plan | vendor, method, effective dates |
| `earning.adjustment` | finance/admin | earning | amount minor, type, reason |
| `payout.review` | finance/admin | payout batch | count, total minor, currency |
| `payout.approve` | finance/admin | payout batch | prior/new state |
| `payout.submit` | finance/admin | payout batch | idempotency reference, provider status |
| `integration.retry` | operations/admin | integration event | attempt, prior/new state, reason |
| `admin.configuration.change` | admin/super-admin | configuration | changed keys and prior/new enabled state |

Command handlers write the audit record in the same database transaction as the domain change.
Provider calls record only sanitized provider IDs and status.

Administrators read these records only through the admin-safe read model described in
[`audit-read-model.md`](audit-read-model.md); raw `metadata_json` is never served.

