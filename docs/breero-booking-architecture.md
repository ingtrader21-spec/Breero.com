# BREERO booking architecture

## Release boundary

This subsystem is production-capable but remains request-only until a separately authorized
release changes the guarded flags. Production defaults are `PROVIDER_ASSIGNMENT_MODE=MANUAL` and
false for `AUTO_ASSIGN_PROVIDER`, `AUTO_CONFIRM_BOOKING`, `PAYMENTS_ENABLED`,
`LIVE_PROVIDER_DISPATCH`, `LIVE_EMAIL_DELIVERY`, `LIVE_SMS_DELIVERY`, `LIVE_CALLBACKS`,
`ODOO_DELIVERY_ENABLED`, and `ODOO_WRITE_ENABLED`.

Account creation and authenticated dashboards do not imply provider approval, assignment,
appointment confirmation, message delivery, callback delivery, or payment authorization.

## Baseline

The master implementation began at commit
`c48e5deb2880657396ce5a9eac51a35ff7ecfdde` on
`codex/breero-production-without-payments`.

Existing foundations retained and extended:

- FastAPI, SQLAlchemy 2, Alembic, PostgreSQL/PostGIS, Redis, Celery, UUID identifiers.
- Argon2 password hashes, short-lived access JWTs, rotating refresh sessions, revocation, and RBAC.
- Catalog, customers, addresses, service areas, bookings, jobs, vendors, workers, dispatch offers,
  assignments, audit logs, and transactional integration outbox.
- Geoapify-backed U.S. address resolution with coordinates and IANA timezone persistence.
- Operator-only scheduling with row/advisory locking, provider credential checks, ZIP/service
  coverage, local provider hours, overlap detection, and audit events.
- BREERO client, provider, operations, and admin Next.js applications sharing the BREERO UI system.

## Trust boundaries

Public clients never submit authoritative coordinates, timezone, coverage, capacity, provider,
price, or status. The API resolves those values and rejects arbitrary state transitions. Public
availability contains customer-safe local windows only. Candidate identities, scores, capacity,
warnings, compliance details, and internal notes are restricted to authorized dispatch/admin roles.

The service address timezone is authoritative. Machine instants are UTC; scheduling records retain
the IANA timezone that gave the local time meaning. Provider headquarters and browser/server
timezones are display preferences only.

## Booking flow

1. Resolve an active, bookable catalog service.
2. Normalize and externally validate the U.S. address.
3. Persist ZIP/ZIP+4, coordinates, validation provenance, and IANA timezone.
4. Resolve an active service zone using exact postal coverage first and spatial coverage where
   configured.
5. Intersect BREERO local operating hours, service rules, provider coverage, professional hours,
   exceptions, current bookings, active holds, buffers, travel estimate, and daily limits.
6. Return public-safe local windows without provider information.
7. Atomically reserve a 30-minute capacity hold under database locking.
8. Create or reconcile the client identity, profile, address, and request in one transaction.
9. In the protected release, place the request in manual dispatch and expose ranked candidates only
   to dispatch/admin users.
10. Assignment, reassignment, cancellation, and rescheduling are state-machine operations that
    release or convert capacity and append audit history atomically.

## Operating policy

BREERO's outer scheduling boundary is 07:00–19:00 in the service-address timezone, Monday through
Saturday. Sunday uses the same clock boundary but is emergency-only and additionally requires an
emergency-eligible service, an emergency-enabled provider professional, and remaining emergency
capacity. BREERO does not represent medical or life-safety emergencies; those requests must be
directed to 911 or the appropriate emergency authority.

## Concurrency

Availability is advisory. A hold or assignment is authoritative only after a transaction obtains
the provider/day and provider/interval lock, removes expired holds from the calculation, rechecks
job-count and minute capacity, and writes the reservation. PostgreSQL exclusion/unique constraints
and advisory locks protect against concurrent overbooking; idempotency keys protect request replay.

## Production activation

Migration, seed, and activation are distinct changes. Before any production migration: back up the
database, record the current Alembic head, restore the backup in isolation, test upgrade/downgrade,
run staging migration and count/constraint checks, and obtain explicit production authorization.
Passing tests does not authorize enabling automatic assignment, confirmation, payments, dispatch,
communications, callbacks, or Odoo writes.
