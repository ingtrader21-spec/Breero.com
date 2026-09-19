# RELEASE RUNBOOK

Release sequence:

```
exact source SHA

↓
CI

↓
immutable container image

↓
SBOM

↓
security scan

↓
image signature/provenance

↓
staging

↓
migration

↓
health/readiness

↓
security tests

↓
E2E

↓
integration tests

↓
approval

↓
production backup

↓
migration preflight

↓
canary

↓
smoke

↓
metrics/log verification

↓
controlled rollout

↓
monitored soak
```

Abort criteria must include:

```
5xx threshold

latency threshold

authentication failures

database failures

outbox/inbox backlog

worker heartbeat

business smoke failure
```

---
