# BREERO repository memory for coding agents

This file is the fast, repository-local starting point for API work. Read it before changing code.

## Working rule

Do not begin with a repository-wide “fix all” change. First:

1. locate the implementation and owning domain;
2. locate the relevant unit, integration, PostgreSQL/PostGIS, security, OpenAPI, and frontend-contract tests;
3. record the exact Git branch, HEAD, `origin/main`, open dependency PRs, and worktree state;
4. identify concrete defects with file and contract evidence;
5. implement one dependency-safe slice on its own branch;
6. run every applicable gate before moving to the next slice.

A route, table, page, or passing unit test is not evidence that a workflow is complete.

## Safety boundaries

- Preserve the existing FastAPI, async SQLAlchemy, PostgreSQL/PostGIS, Alembic, Redis/Celery, Next.js, pnpm, and Turborepo architecture.
- PostgreSQL is authoritative for bookings, holds, capacity, assignments, authorization, and lifecycle state.
- Keep heavy domains in separate branches and PRs.
- Do not activate payments, payouts, automatic booking, automatic assignment, automatic confirmation, live provider dispatch, email, SMS, callbacks, Odoo writes, or external automation as part of ordinary API cleanup.
- Do not touch the live server while auditing or refactoring API code.
- Never report an endpoint as complete without authorization, ownership/tenant scope, persistence, validation, error mapping, OpenAPI, and applicable concurrency/idempotency/audit/outbox tests.

## Review refresh — 2026-09-13

The historical audit below is retained as dated evidence. At this refresh,
`origin/main` is `ee71263bfa609b872f4b96279221d7f349fa7b4a` and schema readiness expects
`022_provider_services_skills`. The original #68/#85–#88 stack has reached
main; use `docs/architecture/CURRENT_SYSTEM.md` and the current open PR list
for ongoing work. This update performs no deployment or database migration.

## Current protected baseline

Audit baseline on 2026-08-27:

```text
repository=appolon1908-hue/Breero.com
main=35beb55eedb3f58eb39caf40ffaa9795978d6ee7
main_schema_readiness=017_provider_credentials
production_deployed_by_this_audit=NO
live_server_changed_by_this_audit=NO
```

This snapshot becomes stale. Re-run the commands below before every new task.

## Git preflight

```bash
git status --short
git branch --show-current
git fetch --all --prune
git rev-parse HEAD
git rev-parse origin/main
git log -5 --oneline --decorate
gh pr list --repo appolon1908-hue/Breero.com --state open
gh pr status --repo appolon1908-hue/Breero.com
```

Do not reuse CI, review, or migration evidence from an older head after a push, rebase, merge, or retarget.

## API implementation map

```text
apps/api/app/main.py
  FastAPI construction, middleware, V1/V2 mounting, health and readiness

apps/api/app/api/v1/router.py
  mounted V1 route families and capability-dependent registration

apps/api/app/api/v2/router.py
  current V2 surface; presently foundation/capability focused

apps/api/app/api/v1/**
  HTTP adapters only: schemas/dependencies/response mapping and service calls

apps/api/app/domains/**
  business models, repositories, services, policies and state transitions

apps/api/app/integrations/**
  provider-neutral and provider-specific external adapters

apps/api/app/workers/**
  asynchronous processing, retries and recovery

apps/api/app/db/**
  async engine/session and SQLAlchemy metadata

apps/api/migrations/versions/**
  Alembic migration lineage

apps/api/openapi.json
  checked-in API contract artifact

apps/api/scripts/generate_openapi.py
  deterministic operation-ID validation and OpenAPI generation

scripts/check-frontend-openapi.mjs
  frontend-required subset and forbidden payment-mutation guard

packages/api-client/**
  shared frontend transport/client boundary
```

Expected call direction:

```text
router -> authorization/dependency -> application/domain service -> repository -> PostgreSQL
```

Do not put long business workflows or external provider calls directly in FastAPI route functions.

## Backend test entry points

Backend pytest configuration is not at the repository root. It is in:

```text
apps/api/pyproject.toml
  [tool.pytest.ini_options]
  testpaths = ["tests"]
```

Primary commands from `apps/api`:

```bash
python -m pip install -e '.[dev]'
ruff check .
mypy app
alembic upgrade head
alembic check
python scripts/check_schema_drift.py
pytest -q
python scripts/generate_openapi.py
```

Important test locations:

```text
apps/api/tests/*.py
apps/api/tests/booking/**
apps/api/tests/integration/**
apps/api/tests/payments/**
```

The required backend workflow also runs release-safety, disabled-capability, canonical lifecycle, negative lifecycle, PostgreSQL concurrency, prior-head migration, dependency, secret, Docker-build, and container-vulnerability gates.

## Frontend and contract test entry points

Root workspace commands:

```bash
pnpm install --frozen-lockfile
pnpm lint
pnpm typecheck
pnpm test
pnpm contract:check
pnpm build
pnpm --filter @breero/web test:e2e
```

Configuration locations:

```text
package.json
apps/web/package.json
apps/web/vitest.config.ts
apps/web/vitest.setup.ts
apps/web/playwright.config.ts
apps/web/tests/**
scripts/check-frontend-openapi.mjs
```

The Playwright suite is expected to run Chromium, Firefox, and WebKit through the required frontend workflow.

## Required CI entry points

```text
.github/workflows/quality.yml
  path classification and final required `quality` aggregator

.github/workflows/backend-production.yml
  backend, database, migration, OpenAPI, security and image gates

.github/workflows/frontend-production.yml
  frontend install, audit, lint, typecheck, tests, contract, build and browser E2E
```

## Current stacked API program

As of this audit, these changes are not in `main` and must be reviewed and merged in dependency order:

```text
#68 be/auth-identity-tenancy-rbac
#85 be/provider-onboarding-api-completion
#86 be/booking-intents-api
#87 be/address-geography-timezone-service-zones
#88 be/provider-services-skills
```

Do not treat a green stacked-branch workflow as proof that the combined release candidate is approved or production ready.

## API-change checklist

Before implementation:

- identify the canonical method/path and compatibility route, if any;
- identify the owning domain and source-of-record table;
- identify authentication, permission, tenant/legal-entity and record policy;
- identify capability, idempotency, request hash, `If-Match`/version, rate-limit, PII and emitted-event requirements;
- identify migration and rollback/forward-fix requirements;
- identify every backend and frontend consumer.

Before review:

- request/response schemas and examples are in OpenAPI;
- operation ID is unique;
- error behavior and required headers are stable;
- positive and negative authorization tests exist;
- PostgreSQL/PostGIS tests cover persisted invariants;
- concurrency/idempotency tests exist for critical mutations;
- audit and transactional outbox behavior is tested where required;
- frontend contract and browser flows pass when affected;
- exact-head CI and current review state are recorded.

## Current audit

See:

```text
docs/audits/2026-08-27-api-audit.md
docs/audits/2026-08-27-api-audit-status.json
```
