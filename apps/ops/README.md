# BREERO Operations Control Center

Target: `ops.breero.com`. Operations and admin accounts only.

Every screen reads the canonical API; the browser never derives business state.
Risk, eligibility, permitted transitions and technician next steps all come from
the server (`apps/api/app/domains/dispatch/control_center.py`, `risk.py`, and
`apps/api/app/domains/jobs/lifecycle.py`).

| Route | Screen | API |
| --- | --- | --- |
| `/` | Operations dashboard | `GET /operations/control-center/summary` |
| `/queue` | Dispatch queue + filters (URL-linkable) | `GET /operations/control-center/queue` |
| `/exceptions` | SLA / at-risk / exception queue | `GET /operations/control-center/exceptions` |
| `/jobs/[jobId]` | Job detail, timeline, diagnostics, work requests, match/assign/reassign, transitions | `GET /operations/control-center/jobs/{id}`, `…/candidates`, `POST /operations/jobs/{id}/match·assign·reassign`, `POST /jobs/{id}/transition`, `POST /jobs/work-requests/{id}/review` |
| `/capacity` | Capacity & workload per worker (UTC day) | `GET /operations/control-center/capacity` |
| `/service-areas` | Privacy-safe service-zone load and coverage | `GET /operations/control-center/service-areas` |
| `/integrations` | Integration failures (no payloads, no retry) | `GET /operations/control-center/integration-failures` |

Every mutation requires a reason where the API records one, and is followed by
a server readback. Reassignment sends the job version the operator reviewed;
a stale view is rejected with `409`.

Types in `lib/types.ts` are app-local mirrors of the API schemas until the
shared `@breero/api-client` covers these routes.

Configuration: `NEXT_PUBLIC_API_BASE_URL` (HTTPS; `http://localhost` is accepted
outside production only).

Dispatch users must not have finance payout approval permissions, and this
console exposes no payment, payout, or integration-retry actions.

```bash
pnpm --filter @breero/ops lint
pnpm --filter @breero/ops typecheck
pnpm --filter @breero/ops test
```
