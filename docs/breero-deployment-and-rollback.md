# BREERO deployment and rollback

## Pre-deployment

Back up PostgreSQL, record `alembic current`, verify all safety flags are false and assignment mode is MANUAL, deploy to staging, run the full test/contract suite, then run `alembic upgrade head`. Validate row counts, constraints, indexes, timezone values, users, bookings, readiness, and smoke workflows before shifting traffic.

## Rollback

Stop traffic to the new application version, deploy the previous immutable image, and run only the reviewed downgrade range (for this change: `alembic downgrade 023_account_setup_notes`) if the previous application cannot tolerate the additive tables. Migrations 024 and 025 remove only newly added administration/phone-verification tables. Restore from the pre-deployment backup instead of attempting an unreviewed destructive downgrade.

After rollback, verify `alembic current`, `/health/ready`, authentication, booking reads, and manual dispatch. Record the incident correlation IDs and preserve audit logs. Never enable payments, automatic assignment, live dispatch, email, SMS, callbacks, or Odoo writes as part of rollback.
