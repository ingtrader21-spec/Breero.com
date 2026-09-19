# P0 IMPLEMENTATION PACKAGE

## P0 Branch 1 — API Foundation

Recommended branch:

```
be/marketplace-v2-p0-api-foundation
```

Implement:

```
V2 router foundation

V2 error handlers

unexpected-error envelope

WWW-Authenticate preservation

Retry-After preservation

CommandContext dependency

request/correlation middleware

ETag/If-Match convention

OpenAPI operation-ID convention
```

Acceptance:

```
P0_API_FOUNDATION=PASS
```

only when all relevant transport/error tests pass.

---

## P0 Branch 2 — Authentication + Identity

```
be/marketplace-v2-p0-authentication
```

Implement:

```
production OIDC enforcement

canonical issuer

JWKS/discovery cache

unknown-kid refresh

external_identities migration

issuer+subject identity binding

local production auth disablement

production configuration validation

.env.example safe placeholders
```

Tests:

```
wrong issuer

wrong audience

expired

nbf

unknown kid

malformed token

missing token

local production login denied
```

---

## P0 Branch 3 — Authorization

```
be/marketplace-v2-p0-authorization
```

Implement:

```
Principal

permissions

provider memberships

worker identity

tenant/legal entity context

record policies

authorized repository methods
```

Mandatory cross-resource denial tests.

---

## P0 Branch 4 — Capabilities + Idempotency + Concurrency

```
be/marketplace-v2-p0-capabilities-idempotency
```

Implement:

```
reuse canonical capability service

guard existing disabled V1 Marketplace operations

server-side command capability guards

idempotency_records

IdempotencyService

request hashing

response replay

version/ETag convention

If-Match support
```

---

## P0 Branch 5 — Audit + Outbox Reliability

```
be/marketplace-v2-p0-integration-reliability
```

Implement:

```
full Audit context

claim-token-safe finalization

lease extension/timeout safety

processed_at vs delivered_at

destination

correlation

causation

event registry

unknown event terminal handling

Ops terminal failure visibility
```

---

## P0 Branch 6 — Durable Inbox + Webhooks

May remain in integration-reliability branch if review scope stays manageable, otherwise separate:

```
be/marketplace-v2-p0-webhook-inbox
```

Implement:

```
integration_inbox migration

provider/event uniqueness

raw hash

signature metadata

timestamp/replay verification

worker claims

lease recovery

retry

terminal failure

manual replay endpoint

manual durable-inbox replay requires `integration.replay`; `integration.retry` is insufficient

provider translator registry
```

No synchronous third-party business mutation inside webhook routes.

---

## P0 Branch 7 — Storage + Uploads

```
be/marketplace-v2-p0-storage-uploads
```

Implement:

```
storage_objects

upload_sessions

ObjectStorage

MalwareScanner

upload APIs

private object access

signed downloads

size/MIME policies

scan/quarantine

cleanup scheduler
```

---

## P0 Branch 8 — Notifications + Exceptions

```
be/marketplace-v2-p0-operations-foundation
```

Implement:

```
notification_intents

notifications

notification_deliveries

NotificationPolicy

operational_exceptions

Ops acknowledge/assign/note/retry/resolve
```

Existing direct email side effects should migrate to notification policy where appropriate.

---

## P0 Branch 9 — Observability + Deployment

```
be/marketplace-v2-p0-observability-deployment
```

Implement:

```
/health/version

PostGIS readiness

worker heartbeat

queue depth/age metrics

OpenTelemetry/equivalent

alert definitions

gateway /api/v2 configuration

public /internal denial

Keycloak/middleware secret configuration

backup automation

restore rehearsal

release manifest
```

---

## P0 FINAL

Do not begin Catalog until:

```
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

P0_DEPLOYMENT=PASS

P0_FINAL=PASS
```

---
