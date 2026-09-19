# BREERO Marketplace V2 — Production Readiness Gates

## Status

Binding evidence contract for declaring a release candidate reviewable, staging-ready, production-ready, or activated.

A green unit-test run, a mergeable pull request, completed documentation, or the existence of code/schema/routes is not production approval.

## Status vocabulary

```text
IMPLEMENTED
= code and migrations exist on a review branch

REVIEWABLE
= exact-head CI evidence is green and the PR package is complete

MERGE_READY
= REVIEWABLE + required independent approval + resolved threads + branch rules satisfied

STAGING_READY
= merged immutable candidate + isolated staging configuration and prerequisites

PRODUCTION_READY
= all mandatory gates below pass for the exact release/configuration/evidence snapshot

CAPABILITY_ACTIVE
= PRODUCTION_READY + separately authorized activation change applied and verified
```

No status implies the next one automatically.

## Exact release identity

Every readiness decision must bind:

```text
source repository
source SHA
pull request(s)
migration head
OpenAPI/contract digest
container image digest(s)
SBOM/provenance/signature evidence
configuration version or digest
capability-state snapshot
secret-reference inventory without secret values
infrastructure target
approval/change record
time of evidence
rollback artifact and procedure
```

Evidence from an earlier SHA, dismissed review, different configuration, different image digest, different migration head, or different infrastructure target is stale.

## Mandatory gates

| Gate | Minimum passing evidence |
|---|---|
| `GATE_ARCHITECTURE` | Binding domain/system-of-record/API/event/authorization boundaries reviewed; no unresolved cross-document conflict; accepted dependency order and non-scope |
| `GATE_DATABASE` | One intended Alembic head; fresh upgrade; upgrade from supported prior heads; practical downgrade/rollback boundary; schema-drift check; PostgreSQL/PostGIS integration evidence; bounded backfill plan where applicable |
| `GATE_AUTHENTICATION` | Canonical issuer, audience/azp/signature/algorithm/time validation, process-wide discovery/JWKS cache, unknown-kid refresh, local-production-auth shutdown, production configuration fail-closed tests |
| `GATE_IDENTITY` | Immutable `(issuer, subject)` binding, external-identity migration/backfill/uniqueness, duplicate/conflict behavior, account-link/recovery policy, audit evidence |
| `GATE_AUTHORIZATION` | Permission and record-policy inventory; tenant/legal-entity isolation; cross-customer/provider/worker negative tests; PII disclosure policy; separation-of-duty tests |
| `GATE_CAPABILITIES` | One authoritative capability service; backend command guards; frontend fail-closed projection; missing/unreadable/false negative tests; no route/schema/mock activates a capability |
| `GATE_IDEMPOTENCY` | Actor/operation/key uniqueness, request hash, replay, in-progress behavior, expiry, different-payload conflict, transaction integration and tests |
| `GATE_CONCURRENCY` | Version/ETag/If-Match policy, stale-write behavior, row-lock/constraint evidence for serialized invariants, PostgreSQL race tests |
| `GATE_AUDIT` | Actor/context/reason/resource/correlation coverage, append-only behavior, redaction, transactional relationship to commands, privileged-access audit tests |
| `GATE_API` | OpenAPI regenerated and drift-checked; stable operation IDs/error contract; V1 compatibility; typed client/contract evidence; rate-limit and authentication headers preserved |
| `GATE_OUTBOX` | Atomic creation, lease/claim token, retry/backoff, stale lease recovery, finalization ownership, destination/correlation/causation, terminal-failure visibility and duplicate-delivery tests |
| `GATE_INBOX` | Provider/event uniqueness, raw hash/auth evidence, claim/lease/retry/terminal states, idempotent translator behavior, replay controls and worker-crash recovery tests |
| `GATE_WEBHOOKS` | Provider-specific signature/token/timestamp/replay verification; unknown event handling; durable receipt before business mutation; no synchronous third-party mutation |
| `GATE_STORAGE` | Private object access, upload session, size/MIME allowlist, checksum, malware scan/quarantine, signed short-lived download, cleanup/retention/deletion and authorization tests |
| `GATE_NOTIFICATIONS` | Notification intent/delivery state, consent/suppression, channel policy, template/version, outbox delivery, callback inbox, duplicate/bounce/failure handling, unrestricted sends disabled by default |
| `GATE_ADAPTERS` | Provider-neutral interface, timeout/retry/circuit behavior, idempotency mapping, secret isolation, sandbox/fake-mode declaration, reconciliation and operational exception behavior |
| `GATE_FRONTEND` | Frozen install, dependency audit, lint, typecheck, unit/component tests, accessibility, responsive coverage, production build, contract check and relevant cross-browser E2E against intended capability behavior |
| `GATE_SECURITY` | Secret scan, dependency/container vulnerability policy, threat-model controls, least privilege, ingress/egress review, headers/TLS, abuse/rate limits, penetration or focused security evidence as applicable |
| `GATE_OBSERVABILITY` | Structured logs with correlation, metrics, traces, queue/lease age, error/latency/SLO alerts, worker heartbeat, dashboards/runbooks, PII/secret redaction verification |
| `GATE_BACKUP` | Dated application/database/object/config backup coverage, retention, encryption/access, artifact identifiers and ownership |
| `GATE_RESTORE` | Restore rehearsal into an isolated target, measured RTO/RPO, integrity/application smoke proof and documented failure/rollback handling |
| `GATE_STAGING` | Isolated PostGIS/Redis/API/workers/frontends, current immutable candidate, DNS/TLS, synthetic multi-persona data, explicit sandbox/provider configuration, no unsafe production reuse |
| `GATE_DEPLOYMENT` | Reproducible manifest, digest-pinned images, secret references, migration ordering, health/readiness, canary plan, maintenance/change record and operator authority |
| `GATE_ROLLBACK` | Tested application rollback, migration compatibility/forward-fix boundary, prior immutable images/config, data-safety decision tree, named owner and abort thresholds |
| `GATE_UAT` | Customer/provider/worker/ops/admin persona journeys, negative authorization, degraded-provider cases, browser matrix, issue disposition and signed acceptance for the exact candidate |
| `GATE_INFRASTRUCTURE` | Capacity/disk headroom, private data-plane ports, approved ingress, current DNS/TLS, monitoring, firewall/network topology and no unresolved critical host safety issue |
| `GATE_GOVERNANCE` | Required independent approval on unchanged final SHA, last-push approval, resolved review threads, unambiguous required checks, release/change approvals and no bypass |

## Required baseline before Marketplace V2 domain expansion

Do not begin Catalog or downstream marketplace domains until the applicable P0 foundation status is proven:

```text
P0_API_FOUNDATION=PASS
P0_AUTHENTICATION=PASS
P0_IDENTITY=PASS
P0_AUTHORIZATION=PASS
P0_CAPABILITIES=PASS
P0_IDEMPOTENCY=PASS
P0_CONCURRENCY=PASS
P0_AUDIT=PASS
P0_OUTBOX=PASS
P0_INBOX=PASS
P0_STORAGE=PASS
P0_NOTIFICATIONS=PASS
P0_OPERATIONS=PASS
P0_OBSERVABILITY=PASS
P0_DATABASE=PASS
P0_SECURITY=PASS
P0_DEPLOYABILITY=PASS
P0_FINAL=PASS
```

`P0_DEPLOYABILITY=PASS` means the foundation is reproducibly deployable and rehearsed in isolated staging. It does not require or authorize a Marketplace V2 production deployment.

## Current high-risk capability posture

Until dedicated implementation, certification and a separate activation approval exist:

```text
payments=false
payouts=false
paid_leads=false
instant_booking=false
automatic_booking=false
automatic_assignment=false
automatic_confirmation=false
provider_self_service=false
marketplace_matching=false
messaging=false
reviews=false
marketing=false
unrestricted_email=false
unrestricted_sms=false
external_automation=false
```

The accepted quote-only/operator-confirmed scheduling baseline may retain its approved request intake and manual scheduling routes. That does not change the disabled values above.

## Pull-request evidence gate

Every implementation PR must provide, where applicable:

```text
starting main SHA
final exact head SHA
commit inventory
changed domain/API/event/permission/capability inventory
migration head and upgrade/downgrade evidence
PostgreSQL/PostGIS tests
unit/domain tests
negative authorization/security tests
idempotency/concurrency tests
OpenAPI and typed-client evidence
frontend lint/type/test/build/E2E evidence
outbox/inbox/adapter failure evidence
observability and operational documentation
rollback procedure
unresolved risks
```

CI green is necessary but not sufficient. A push after approval invalidates stale approval according to repository rules and requires review of the new exact head.

## Staging and production environment gate

Before staging or production action, revalidate rather than reuse stale host observations:

```text
current listener/port inventory
current disk/capacity inventory
current DNS/TLS
current container/image/config inventory
current database revision
current backup/restore evidence
current secrets/provider readiness
current monitoring/alert state
```

No global Docker prune, port mutation, database migration, DNS change, proxy reload, or secret write is authorized merely by this document.

## Go / no-go decision

A release record may state:

```text
PRODUCTION_READY=YES
```

only when every mandatory gate for that release is `PASS`, evidence is bound to the exact release identity, all P1/P0 blockers are resolved or formally dispositioned without weakening safety, and required human approvals are valid.

A capability may state:

```text
CAPABILITY_ACTIVE=YES
```

only through a separately reviewed activation change that names the exact capability, environment, release, dependencies, monitoring, canary, rollback and authorizing owner.

Otherwise:

```text
PRODUCTION_READY=NO
CAPABILITY_ACTIVE=NO
```

## Current known governance blocker

Repository issue #45 tracks the ambiguous/missing required `quality` check context. Until the workflow/ruleset contract is repaired and verified across code and documentation PR classes, do not treat a mergeable UI state as proof that `GATE_GOVERNANCE` passed.

Documentation completion does not deploy, migrate production data, merge a PR, or activate any capability.
