# Analytics projections (PAS-130 / M23)

Status: **partial — independent slice only.** PAS-130 stays open until PAS-129
(Finance) and PAS-128 (Reviews) provide certified sources and the exit gate is
proven at the final implementation head.

## Authority

- PostgreSQL source-of-record tables remain the only authority. The analytics
  domain (`apps/api/app/domains/analytics`) owns no tables, performs no writes,
  and emits no events.
- Each response is computed inside one read-only `REPEATABLE READ` snapshot, so
  all groups in a response agree with each other.
- Superset or any other BI tool must read the same projection or read replicas;
  it must never own transactional state.

## Endpoints

| Method | Path | Permission | Tenant scope |
|---|---|---|---|
| GET | `/api/v1/analytics/marketplace/metrics` | `analytics.marketplace.read` (ops_manager, admin, superadmin) | Internal global/brand assignment and **no** vendor-scoped assignment; otherwise `403 ANALYTICS_SCOPE_DENIED` |
| GET | `/api/v1/analytics/provider/metrics` | `analytics.provider.read` (vendor_admin) | The caller's provider organization only; `403 PROVIDER_SCOPE_REQUIRED` without one |

Query: `start`, `end` (timezone-aware ISO-8601; default last 30 days ending at
snapshot time; at most 366 days; `422 INVALID_ANALYTICS_WINDOW` otherwise).

## Freshness contract

- `generated_at`: database snapshot time.
- `groups[].source_watermark`: latest source-row change inside scope and window
  (`null` when there is none).
- `projection.max_age_seconds` (300): clients mark the view stale after this.
- Rates are `null` when the denominator is zero. Clients must not substitute 0.

## Metric coverage

| Group | Status | Source | Provider scope |
|---|---|---|---|
| request | available | `booking_intents` | restricted (anonymous) |
| qualification | available (current status only) | `booking_intents` | restricted |
| matching | available | `jobs` | restricted (pre-assignment) |
| opportunity | available | `dispatch_offers` | own offers |
| quote | available (counts only; amounts are finance) | `work_requests` + `jobs` | own jobs |
| booking | available | `bookings` (+ `jobs` for provider) | bookings whose job is assigned to the provider |
| utilization | **unavailable** | no capacity-minutes projection | — |
| completion | available | `jobs` | own jobs |
| cancellation | available | `bookings` | own bookings |
| review | **unavailable — PAS-128** | none | — |
| response_time | available | `dispatch_offers` | own offers |
| finance | **unavailable — PAS-129** | none certified | — |

## Frontend

`/ops/analytics` (marketplace) and `/provider/analytics` (provider) render
loading, restricted, error/retry, degraded (last result kept), empty-window and
stale states. The mock API refuses to synthesize analytics.

## Remaining work

1. Finance metrics after PAS-129 certifies ledger/earnings/payout projections.
2. Review metrics after PAS-128 provides a review source of record.
3. Utilization once a capacity-minutes source is defined.
4. Stage-history events for qualification funnels (current-status only today).
5. Drill-down lists: no scoped list contracts exist yet for these groups.
6. Materialized projections/read replica and Superset datasets if query cost
   requires it; exit-gate proof at the final head.
