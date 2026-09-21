# BREERO staging email certification

This runbook certifies the tenant email workflow without granting any production deployment capability.

## Required staging endpoints

- `STAGING_WEB_BASE_URL=https://staging.breero.com`
- `STAGING_API_BASE_URL=https://api-staging.breero.com`

The certification harness rejects non-HTTPS URLs and rejects any hostname outside the approved BREERO staging namespace.

## Read-only certification

Run `node scripts/certify-staging-email.mjs` with the two staging URLs. The harness verifies:

1. the staging web login route is reachable;
2. API `/health/ready` reports `status=ready`, PostgreSQL `ok`, schema `ok`, and Redis `ok`;
3. `/api/v1/auth/login-mode` returns the active staging identity contract.

With `STAGING_ACCESS_TOKEN` it additionally verifies:

4. `/api/v1/auth/context` returns a valid authorized dashboard and permission set;
5. tenant-scoped email domains, senders, credential metadata and outbox endpoints are readable for that identity;
6. credential and outbox responses do not expose password, secret reference, SMTP password, or API-key material.

## Controlled compose canary

Writes are disabled by default. To exercise the full authenticated staging chain, explicitly set:

- `STAGING_ALLOW_EMAIL_CANARY=1`
- `STAGING_ACCESS_TOKEN`
- `STAGING_CANARY_SENDER_ID`
- `STAGING_CANARY_CREDENTIAL_ID`
- `STAGING_CANARY_RECIPIENT`

The supplied sender and credential must already belong to the authenticated tenant scope. The credential must report a configured runtime secret reference and the sender's domain must already be `VERIFIED`.

The harness then performs exactly one idempotent staging compose and proves that the backend creates a durable email outbox event for the returned message. It does not change domain verification, create credentials, alter tenant access, deploy containers, or target production.

## Browser certification

`apps/web/tests/e2e/tenant-email.spec.ts` covers the browser workflow in the repository's three Playwright projects:

`/login -> /admin -> /admin/email -> domain -> verification -> sender -> credential reference -> compose -> outbox`.

For deployed staging, the existing Playwright configuration accepts `E2E_BASE_URL` so the suite can point at a real staging web deployment rather than starting the local mock server.

## Hard gates

Certification is not complete unless all of these are true:

- exact-head Required Quality executes on a real GitHub Actions runner and passes;
- PostgreSQL migration/Alembic/schema-drift and backend pytest pass at the same accepted backend SHA;
- frontend frozen install/audit/lint/typecheck/tests/build pass at the accepted frontend SHA;
- Chromium, Firefox and WebKit Playwright pass at the accepted frontend SHA;
- staging DNS is resolvable and the staging web/API endpoints are reachable;
- the read-only staging certification passes;
- the controlled compose canary passes when explicitly authorized and supplied with real staging-only credentials.

A GitHub Actions job that receives no runner and executes zero steps is infrastructure-blocked evidence, not a code pass or code failure. An unreachable staging hostname is likewise a staging-connectivity blocker, not a successful certification.
