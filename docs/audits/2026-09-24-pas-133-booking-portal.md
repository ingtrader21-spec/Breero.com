# PAS-133 — customer booking portal slice

## Scope and preflight

Agent 3 worked only in `pas-133-agent3-codex`, branch
`appolon1908/pas-133-m26-complete-product-portals`, from exact base
`5992759bfb8bc63fe030cefbfcac0a3024c35c78`. The initial worktree was clean;
HEAD and fetched origin/main both matched the base. No other worktree was
modified. Final commit and checks are recorded in the PAS-133 Linear update.

Read PAS-133, blocking PAS-132 (Backlog), and the Notion M00–M30 execution
board. M26 remains **BLOCKED for completion**. This independently testable
frontend slice does not require cross-platform effects, but does not satisfy
the full mission's persona/integration exit gates.

Open PRs checked before implementation: #140 PAS-111 design convergence,
#139 continuation entrypoints, #117 Horizon, #110 secure portal runtime,
#109 portal read models, #70 email, #67 design governance, #65 preflight,
#41 backend bootstrap. Read the #140 and #110 branch diffs; do not duplicate
their shared styles, security runtime, or partner/ops/admin workspaces.
Canonical remote: `ingtrader21-spec/Breero.com` (historical owner redirects).
Dependency PR heads read during execution: #140
`86dcf263cd214e74bc4f162d9942c944926814d9`; #110
`af6067e4872c313f83fe7df8526f5a5a35dd1de0`; #109
`2a377363c6b81210f90692a779751bb18fc335e1`.

## Persona audit at the base

| Persona | Existing source and route | Gap / next owner |
|---|---|---|
| Customer | `apps/web/app/account`: overview, bookings, quotes, profile, addresses, payments | Booking list discards pagination; expired records treated as active; late detail responses can replace current record; cancellation affordance exceeds backend eligibility. This slice repairs booking reads and existing cancellation feedback. Other customer workflows still need acceptance. |
| Provider organization | `/provider` uses `DepartmentDashboard`; `apps/partner/app/page.tsx` uses `PortalApp` with provider-scoped paths | Web module cards have no workflow destinations. Reuse/reconcile #109/#110 after PAS-112 security acceptance. |
| Worker | `/worker`: profile, schedule, availability, jobs module definitions | Permission-aware overview only; no linked worker workflow. Needs worker-scoped read/action contracts and assignment/job gates. |
| Operations | `/ops` module overview; separate `apps/ops` portal | Reuse #109/#110 read models/runtime. Dispatch, assignment and cross-tenant persona tests outstanding. |
| Support | `/support` module overview | No linked case/communication workflows. Depends on support and authorized conversation contracts, plus PAS-132 delivery evidence. |
| Trust | `/trust-safety` module overview | Credential/review/audit module descriptions do not prove record workflows. Needs scoped evidence and escalation contracts. `/trust` is public content. |
| Finance | `/finance` module overview; `apps/admin` includes earnings and explicit unavailable modules | Payment/refund/dispute/payout read projections incomplete. Payments/payouts remain disabled; PAS-132 reconciliation remains a completion gate. |
| Admin | `/admin` includes access assignments; separate `apps/admin` portal | Audit/capability/integration overview modules and #110 work need convergence. Access/session security remains Agent 2's scope. |

Existing relevant tests: `components/portal/*.test.*`, `lib/portal.test.ts`,
`tests/e2e/customer-account.spec.ts`, responsive/accessibility specs;
backend `tests/test_customer_api_structure.py` and customer booking
lifecycle/ownership coverage. Existing mocked account E2E is not live
persona authorization evidence.

## Contract and ownership

- List: `GET /api/v1/customer/bookings?page=1&page_size=20` returns
  `Page<Booking>` with total, page and page_size. Backend explicitly scopes
  by `customer_for(session, current_user)` and `Booking.customer_id`.
- Detail: `GET /api/v1/customer/bookings/{booking_id}` applies the same scope,
  returning 404 when unavailable to the customer.
- Existing cancellation: `POST /api/v1/customer/bookings/{booking_id}/cancel`
  returns the persisted booking. Backend locks booking/job, validates both
  states, releases holds, records audit and commits. UI state eligibility
  is only an affordance; backend job-state validation remains authoritative.
- Implementations: `apps/api/app/api/v1/customer/bookings.py`, schemas and
  dependencies beside it, `domains/booking/models.py`, and existing
  `packages/api-client/src/client.ts`. No endpoint or response was invented.
- No API client, auth/session/PKCE/BFF file, shared UI/token authority, backend,
  OpenAPI, database, migration, capability flag or production config changed.
- PAS-112 interface dependency: retain `customerApi.bookings.mine/getMine/
  cancelMine` and typed `ApiError` semantics when replacing transport with the
  approved same-origin BFF. Current base transport is not secure-portal
  completion evidence. PAS-111 owns shared components/tokens; this slice only
  adds page layout CSS using current tokens.
- Migration remains `031_provider_catalog`; OpenAPI SHA-256 unchanged:
  `a2847e6e1c3c2e9b4eba7ed88e86cdc64437712d2b162483b9bf003521357b36`.

## Implemented UI behavior

- LOADING: named status, prior record hidden on route/page changes and retry.
- EMPTY: actual empty response or no matching records on current page.
- READY: API records, backend status labels, amounts and encoded detail links.
- ERROR: sanitized messages, retry, back navigation for unavailable detail.
- RESTRICTED: 401 sign-in recovery and 403 support path, no blind retry loop.
- DISABLED: cancellation unavailable outside the backend's eligible booking
  states; terminal/unknown states fail closed. No payment collection flow
  is advertised in this workspace.
- DEGRADED: connection/timeout/unavailable/rate-limit failure with retry;
  stale records are not presented as current.
- Pagination uses backend metadata; active/history explicitly filter the
  current page because the API has no status filter. No invented totals.
- Arrival times explicitly use the device timezone; a service-address timezone
  cannot be inferred from the current response contract.

## Evidence and remaining gates

Regression suite first reproduced 15 failures (3 pre-existing behaviors
passed). The repair passed all 18 booking tests. Final workspace lint and typecheck
passed; workspace tests passed (126: web 87, API client 28, UI 9, types 2).
The 44-path frontend contract check and all eight workspace build tasks
passed. The final production-server browser run passed all 15 tests across
Chromium, Firefox and WebKit, covering 320/768/1440 widths. Exact HEAD
is recorded in Linear with the commit. The legacy whole-site E2E suite and
full authenticated persona suite were not rerun locally; CI remains a
separate exact-head gate.
A separate read-only review found a missing CI invocation; wiring the new
suite into `test:e2e` resolved it. No important review findings remain.

Reproduce:

```sh
pnpm lint
pnpm typecheck
pnpm test
pnpm contract:check
pnpm --filter @breero/web exec playwright install chromium firefox webkit
pnpm --filter @breero/web exec playwright test -c playwright.bookings.config.ts
```

The dedicated browser suite uses the real HTTP client with intercepted,
local-only test fixtures and no production API effects. It checks 320/768/1440
widths, keyboard navigation, content accessibility, restricted access and
outage recovery across Chromium/Firefox/WebKit. This proves independent UI
behavior, not backend authentication, tenant isolation, or PAS-132 integration.
The required `test:e2e` command also runs this suite after the existing suite.
Local WebKit required `libavif16`, `libmanette-0.2-0`, `libyuv0` and
`libgav1-2`; they were extracted under `/tmp/pas133-browser-libs`.
Its bundled launcher overrides `LD_LIBRARY_PATH`, so a browser copy under
`/tmp/pas133-browsers` received those libraries in `minibrowser-wpe/sys/lib`.
Verification used `PLAYWRIGHT_BROWSERS_PATH=/tmp/pas133-browsers` and
`LD_LIBRARY_PATH=/tmp/pas133-browser-libs/extracted/usr/lib/x86_64-linux-gnu`.
No system packages or shared browser files were changed. The first
browser run identified a back-link contrast failure; the page now uses the
existing darker brand token. The browser suite uses a production build and local server to avoid
Next development Fast Refresh interrupting keyboard navigation. It keeps a
15-second assertion timeout for browser startup variability.

Remaining: reconcile PAS-112/PAS-111; finish other persona contracts/screens;
prove all-persona authenticated E2E and PAS-132 cross-platform contract,
replay and reconciliation gates at the combined candidate HEAD. Do not mark
PAS-133 Done or check/strike M26 on the execution board.

No deployment, email, SMS, payments, payouts, auto-assignment or integration
activation. Recovery is to revert this isolated frontend commit; no database
rollback is required.
