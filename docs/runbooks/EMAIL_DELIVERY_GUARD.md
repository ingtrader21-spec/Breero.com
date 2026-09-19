# Email delivery guard and recovery

`LIVE_EMAIL_DELIVERY=false` is the new default-off transport gate. Both the legacy
HTTP adapter and SMTP gateway require it, `EMAIL_ENABLED=true`, and
`TRANSACTIONAL_EMAIL_MODE=controlled_canary` before opening a transport. SMTP also
rechecks after thread dispatch. Production Settings rejects live-email activation
until separately certified. These controls do not implement recipient allowlists
or authorize a canary. Explicit fake gateways remain available to isolated tests.

Missing HTTP/SMTP configuration or disabled delivery raises the bounded diagnostic
`EMAIL_DELIVERY_DISABLED`. The HTTP adapter no longer records a local no-op as
successful event delivery. Pending account/provider invitations reflect the live
switch when choosing their initial delivery state.

## Durable parking

Outbox processing retains disabled events as `PENDING_CONFIGURATION`, with payload,
identity, attempt count and safe diagnostic intact. It clears the lease and leaves
`processed_at` unset. Even an event already at the retry limit is parked instead
of discarded into terminal failure. Normal claims exclude this state.

The existing finance/admin integration failures endpoint also lists parked events.
Its existing authorized retry command accepts configuration-pending events and
records the actor in `integration.retry`. No permissions are expanded. Retrying
while disabled parks the event again without transport calls. Activation alone
does not bulk replay parked email; operators must review consent, suppression,
token expiry, recipient and event relevance before explicit replay. Expired
verification/invitation tokens need the appropriate reissue workflow.

The new exception marker `pending_configuration` is handled before
retry exhaustion. Existing retryable and terminal failure behavior is preserved
for errors without that marker. Middleware's existing public-submission parking
and activation behavior is unchanged.

## Operational limits

This guard enforces process configuration, not instant revocation across running
instances or an already-submitted message. Restart/drain through approved release
procedures when configuration changes. Reconcile provider delivery records for
messages already in flight; do not assume disabling transport recalls them.

BREERO still has legacy direct HTTP/SMTP implementations. This PR constrains their
use; it does not certify them as Klyrow integration or replace the required
BREERO outbox -> Middleware -> Klyrow path. Provider idempotency, signed callbacks,
consent/suppression enforcement, recipient controls and delivery reconciliation
remain release requirements. No live delivery or production activation is included.

## Verification and rollback

Unit tests use mocked transports to prove each gate blocks network construction,
same-instance retries recheck configuration, SMTP checks after thread dispatch,
and unconfigured HTTP cannot report local success. An isolated PostgreSQL test
proves parking beyond the retry limit, visible recovery state, repeated denial,
and audited replay using mocked HTTP. The full suite checks existing behavior.

No migration is required. Preserve parked records and event IDs on rollback.
Reverting removes transport guards; keep email workers/transports operationally
suspended until equivalent controls are restored. Do not bulk mark parked events
as delivered or replay historical mail to validate a rollback.
