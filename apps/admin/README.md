# BREERO Admin & Finance Portal

Target: `admin.breero.com`

Keycloak remains the identity authority. This portal manages Breero-owned state only.

## Screens

| Route | Purpose | API |
| --- | --- | --- |
| `/users`, `/users/[userId]` | Search/filter users, detail, effective access, role/access editor, disable/reactivate with confirmation | `/admin/users/**`, `/auth/access/catalog` |
| `/providers`, `/providers/[applicationId]` | Provider application review: approve, reject, request information | `/admin/provider-applications/**` |
| `/geography`, `/geography/zones/[zoneId]` | Service zones: list, create, coverage, update (If-Match), deactivate/reactivate | `/admin/service-zones/**` |
| `/geography/postal-codes` | Postal-code rows: list, add, deactivate/reactivate, validated CSV import (Idempotency-Key) | `/admin/postal-codes/**` |
| `/finance` | Pending payout totals, earnings by status, finance exceptions | `/finance/status`, `/finance/earnings/summary`, `/finance/exceptions` |
| `/finance/payouts`, `/finance/payouts/[batchId]` | Payout batches: candidates review, create, four-eyes approve, submit, history readback | `/finance/payout-candidates`, `/finance/payout-batches/**` |
| `/finance/payments` | Read-only payment and refund inventory | `/finance/payments`, `/finance/refunds` |

No map is rendered for service zones: a tile map would send coverage coordinates
to a third-party host. Payout commands appear only while the API reports
`PAYOUT_ENABLED`; refund issuance, payment capture and live payout transfer are
reported as `NOT_IMPLEMENTED` and have no controls.

Tests: `pnpm --filter @breero/admin test` (Vitest, node environment, components rendered with `react-dom/server`).
