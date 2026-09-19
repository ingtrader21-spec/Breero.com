# Payout capability enforcement

The existing `PAYOUT_ENABLED` setting defaults to false. FinanceService checks it
on each earning-release, batch-create, batch-approve and batch-submit command,
before querying, locking, committing or calling a gateway. A disabled command
raises HTTP 503 with `detail: "payouts_disabled"`. Existing authorization still
applies to HTTP routes. No API route, response model or feature default changes.

Celery finance tasks use the same service. When disabled they fail visibly with
that error; they do not report zero work, no candidates or successful payment.
Retried tasks recheck the setting. This intentionally makes attempts to run the
uncertified payout workflow visible in existing task failure monitoring.

Earning recognition, compensation snapshots, corrective adjustments and finance
reads retain their existing behavior so liabilities and corrections can still be
recorded while settlement is disabled. Existing batches and events are retained;
the guard adds no failed transfer, audit or outbox record for a rejected command.

## Verification and recovery

Run the complete backend suite against an isolated migrated PostgreSQL/PostGIS
database. Guard tests prove all four commands avoid database and gateway calls,
already-created service instances recheck the flag, queued Celery calls fail,
and enabled no-candidate validation is preserved. The PostgreSQL test proves a
blocked approved batch remains unchanged and can subsequently proceed using an
explicitly injected fake gateway in test configuration.

This is enforcement of the current process configuration, not a distributed
instantaneous kill switch. Environment changes require the approved process
restart procedure. It cannot revoke a command already in flight or undo a transfer
already submitted; drain workers and reconcile external state before recovery.
No live payout provider is certified or activated by this change. Existing
production configuration validation continues to reject payout activation.

After a separately approved activation, reconcile retained earnings and batches
before explicit replay. Preserve existing idempotency keys; never fabricate a
settled state from a blocked attempt. Existing payout authorization, separation
of duties, concurrency and ledger certification remain separate workstreams.

## Rollback boundary

No migration is required. Revert the eventual squash commit only through normal
release governance. Reverting removes these guards, so keep finance schedules and
payout commands operationally suspended until equivalent enforcement is restored.
This PR performs no deployment or capability activation.
