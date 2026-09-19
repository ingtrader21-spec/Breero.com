# BREERO 24-PR Consolidation Implementation Plan

> **Execution rule:** Work one task at a time from the current protected `main`. After each task, obtain exact-head green CI and a fresh independent approval, merge, verify post-merge `main`, then refresh every later task. Never batch merges.

**Goal:** Give each remaining historical BREERO PR an evidence-backed disposition while safely preserving unique logic through small, current, tested replacement PRs.

**Architecture:** Current protected `main` is authoritative. Historical PR branches are evidence sources, not merge authorities. Unique changes are replayed into isolated branches following existing FastAPI/domain/repository and Next.js/shared-package boundaries. Capability activation and deployment are outside scope.

**Stack:** Python/FastAPI, async SQLAlchemy, Alembic, PostgreSQL/PostGIS, Redis/Celery, TypeScript/Next.js, pnpm/Turborepo, Docker Compose, GitHub Actions.

**Approved specification:** `docs/superpowers/specs/2026-09-19-breero-pr-consolidation-design.md`

**Planning baseline:** `origin/main=93d72d032d8a382e15f0869f51dc42b7722926d9` after PR #124. Refresh before execution.

## Global gates

For every task:

```bash
git fetch origin --prune
git status --short
git rev-parse origin/main
gh pr list --repo ingtrader21-spec/Breero.com --state open
```

Use an isolated worktree created from the refreshed `origin/main`. Do not reuse a worktree from another task. Record the original PR head, merge-base, current main, changed files, checks, reviews, unresolved threads, and patch disposition.

Applicable backend gates:

```bash
cd apps/api
ruff check .
mypy app
python -m compileall app
alembic upgrade head
alembic check
python scripts/check_schema_drift.py
pytest -q
python scripts/generate_openapi.py
```

Applicable frontend gates:

```bash
pnpm install --frozen-lockfile
pnpm lint
pnpm typecheck
pnpm test
pnpm contract:check
pnpm build
pnpm --filter @breero/web test:e2e
```

CI/deployment changes also require workflow syntax, secret scan, dependency/license policy, Docker/Compose validation, image build, runtime identity, and high/critical image scan gates.

No task proceeds with failing required checks, unresolved Important/Critical review findings, stale approval, non-linear migrations, generated-contract drift, or uncertain ownership.

## Task 1: Create the consolidation ledger

**Files:**

- Create: `docs/production-readiness/BREERO_PR_CONSOLIDATION_LEDGER.md`
- Create: `artifacts/pr-consolidation/ledger.v1.json`
- Create: `scripts/pr_consolidation/validate_ledger.py`
- Create: `scripts/pr_consolidation/test_validate_ledger.py`
- Modify: `.github/workflows/quality.yml` only if the existing classifier does not run the validator for these paths.

**Steps:**

1. Write failing validator tests requiring all 24 PR numbers, unique disposition, original head/base, owning domain, dependency list, affected contracts, replacement PR/SHA fields, and evidence status.
2. Run the focused test and confirm it fails because the ledger is absent.
3. Implement the validator and seed the ledger using GitHub/local Git evidence.
4. Classify each PR as `candidate`, `replacement_required`, `stacked`, `superseded`, or `unsafe` without closing or modifying any PR.
5. Run the validator, scope tests, whitespace, JSON parse, and secret scan.
6. Commit, push, obtain review, merge, and verify the ledger on `main`.

## Task 2: Reconcile PR #41 — backend bootstrap

**Original files:**

- `.github/workflows/backend-bootstrap-tool.yml`
- `scripts/bootstrap_breero_backend.py`
- `scripts/tests/test_bootstrap_breero_backend.py`

**Steps:**

1. Compare PR #41's final patch with current bootstrap and CI behavior.
2. Add failing tests for every still-missing fail-closed behavior: required executables, dependency installation failures, database readiness, idempotency, and redacted diagnostics.
3. Replay only missing behavior on a fresh branch.
4. Run focused bootstrap tests, workflow syntax, Python compile, scope classification, and relevant security gates.
5. Merge the replacement/current PR, verify `main`, update ledger, and close #41 with replacement evidence if it was not merged directly.

## Task 3: Reconcile PR #60 — settings boundaries

**Files:**

- `apps/api/app/config.py`
- `apps/api/app/settings/{__init__,environment,model,release,secrets}.py`
- `apps/api/tests/test_settings_structure.py`

**Steps:**

1. Characterize current Settings public imports and all environment consumers.
2. Add failing structure and behavior tests proving identical defaults, validation, secret handling, and production fail-closed rules.
3. Extract modules without changing the public `Settings` contract.
4. Run focused tests, Ruff, mypy, full pytest, production-config tests, OpenAPI generation, and backend CI.
5. Merge, verify main, and update the ledger.

## Task 4: Reconcile PR #65 — secure deployment preflight

**Files:**

- `.github/workflows/deployment-preflight.yml`
- `deploy/production/SECURE_DEPLOYMENT_SCAFFOLD.md`
- `deploy/production/runtime-paths.example.env`
- `docker-compose.production.yml`
- `scripts/deploy/**`
- `scripts/ci/{classify-quality-scope.sh,test-classify-quality-scope.sh}`

**Steps:**

1. Prove the workflow is read-only and cannot deploy or print secrets.
2. Add failing validator tests for missing paths, unsafe permissions, mutable image references, writable containers, host port exposure, and absent evidence.
3. Replay current-safe preflight logic only.
4. Run shell tests, Python tests, workflow parsing, Compose render, secret scan, and orchestrator contract.
5. Merge and verify; no environment mutation is allowed.

## Task 5: Reconcile PR #55 — public submissions

**Files:** `apps/api/app/api/v1/public_forms.py`, `apps/api/app/domains/public_submissions/**`, `apps/api/app/core/errors.py`, related API integration tests, affected web forms.

**Steps:**

1. Inventory every public form consumer and persisted field.
2. Add RED tests for consent persistence, idempotency replay/conflict/expiry, rate limiting, validation, safe error envelopes, PII exclusion, and duplicate submissions.
3. Implement missing behavior in domain services, not route functions.
4. Run PostgreSQL integration tests, authorization/security tests, OpenAPI, frontend contract, affected web tests, and full backend/frontend gates.
5. Merge and verify before API refactors begin.

## Task 6: Reconcile PR #58 — operations API boundaries

**Files:** `apps/api/app/api/v1/operations.py`, `apps/api/app/api/v1/operations/**`, `apps/api/tests/test_operations_api_structure.py`.

**Steps:**

1. Snapshot methods, paths, operation IDs, dependencies, permissions, responses, and errors.
2. Add a structural test that fails on the pre-split module and behavior tests that prevent contract drift.
3. Split by bookings, credentials, dispatch, workforce, and router responsibility while preserving compatibility imports.
4. Run focused tests, full backend suite, OpenAPI byte/digest comparison, and frontend contract tests.
5. Merge and verify.

## Task 7: Reconcile PR #59 — jobs/work-request boundaries

**Files:** `apps/api/app/api/v1/jobs.py`, `apps/api/app/api/v1/jobs/**`, `apps/api/tests/test_jobs_*`.

Repeat Task 6's contract-preserving refactor process. Explicitly test tenant scope, transition authorization, invalid state changes, pagination, errors, and compatibility imports. Avoid carrying unrelated package/lockfile changes unless current tests require them.

## Task 8: Reconcile PR #62 — endpoint policy registry

**Files:** `apps/api/app/api/policy_registry.py`, `apps/api/endpoint-registry.json`, `apps/api/app/main.py`, integration adapter contracts, registry tests, OpenAPI tooling.

**Steps:**

1. Generate the current route inventory and identify unowned or conditionally registered endpoints.
2. Add RED tests for missing ownership, missing authentication/capability declarations, duplicate operations, and OpenAPI/registry drift.
3. Implement fail-closed registry validation without activating dark routes.
4. Run all backend, OpenAPI, route policy, frontend contract, and security gates.
5. Merge and verify.

## Task 9: Reconcile PR #105 — worker isolation

**Files:** `apps/api/app/db/worker_session.py`, `apps/api/app/workers/tasks.py`, `apps/api/app/observability.py`, worker lifecycle tests and runbook.

Add RED tests proving per-process engine ownership, cleanup, retry behavior, trace propagation, and no request-loop engine reuse. Implement the smallest current-compatible isolation. Run Redis/Celery and PostgreSQL integration tests in addition to full backend gates.

## Task 10: Dispose PR #100 against accepted security remediation

Compare every manifest and lockfile change in #100 with current `main`, current Dependabot state, and the accepted security remediation. If no unique fix remains, update the ledger and close as superseded. If a unique license/dependency policy correction remains, replay it in a focused replacement PR with frozen install, unit/browser tests, audit, license policy, build, and image scans.

## Task 11: Reconcile PR #102 — Keycloak registration/recovery authority

**Files:** `apps/api/tests/test_auth_access_contract.py`, `docs/identity/KEYCLOAK_REGISTRATION_RECOVERY.md`, and current auth code only if tests identify a real gap.

Add RED tests for authoritative Keycloak mode, forbidden local registration/password mutation, issuer/audience verification, safe recovery routing, and local-mode compatibility where explicitly supported. Update documentation to current `auth.codestra.co`. Run complete auth/security tests and negative authorization cases.

## Task 12: Reconcile PR #101 — production Compose

**Files:** production/backend/middleware Compose definitions, example env files, Celery preflight, orchestrator contract, Compose tests.

Define one source of truth for services and overlays. Add RED render tests for duplicate services, mutable images, missing health checks, root users, writable roots, exposed private ports, missing resource limits, and capability activation. Replay only current-safe configuration. Run Compose rendering, image builds/scans, runtime metadata, backend tests, and orchestrator contract. Do not deploy.

## Task 13: Decompose and close PR #123 — live-runtime reconciliation

**Files:** all 132 changed files are evidence sources only.

1. Produce `artifacts/pr-consolidation/pr-123-decomposition.json` mapping every changed file to `already_on_main`, `owned_by_task`, `unique_safe`, or `unsafe_obsolete`.
2. Validate that every `unique_safe` item has a named focused task/replacement PR.
3. Do not cherry-pick, merge, or rebase #123 wholesale.
4. After all unique safe changes are accepted elsewhere, update the ledger and close #123 with links and final SHAs.

## Task 14: Reconcile PR #109 — portal read models

**Files:** portal/access/finance/integration APIs and their domain services/repositories/tests.

Implement through RED tests for tenant/legal-entity scope, role permissions, record ownership, PII minimization, pagination, database persistence, outbox/audit behavior, and forbidden cross-tenant reads. Run full PostgreSQL, auth, OpenAPI, and backend gates.

## Task 15: Rebuild PR #115 — generated OpenAPI contracts

After #109 merges, regenerate from accepted `main`; never copy the old generated artifact. Retarget the replacement to `main`. Test deterministic regeneration, clean working tree after a second generation, TypeScript compilation, client transport behavior, frontend contract, and all builds.

## Task 16: Reconcile PR #110 — portal BFF runtime

**Files:** partner/ops/admin layouts, server routes, workspaces, shared portal/auth packages, portal release workflows.

Add RED tests for server-side token ownership, cookie flags, callback validation, CSRF/state/nonce, logout, role routing, API allowlists, error redaction, and denial of browser-held service credentials. Run all app unit tests, contract checks, builds, E2E, Docker and security gates.

## Task 17: Reconcile PR #69 — role-aware dashboards

Build only on accepted #109/#115/#110 contracts. Test login routing, department/role authorization, access denied behavior, cross-role navigation denial, loading/error/degraded states, and responsive browser flows. Merge only after all portal applications pass.

## Task 18: Select one UI authority from PRs #67 and #117

**Files:** global layouts/styles, shared headers/footers, design-system docs/workflow, admin/ops/partner/web shells.

1. Create a component/token/route overlap matrix.
2. Choose one shell based on current portal compatibility, accessibility, responsiveness, bundle/build impact, and maintainability.
3. Add visual-contract and accessibility tests before changing the shell.
4. Replay only compatible unique components from the other PR.
5. Merge one replacement PR, then close both historical PRs with evidence.

## Task 19: Reconcile PR #70 — tenant email backend

**Files:** `apps/api/app/domains/tenant_email/**`, email/integration routes, workers, auth dependencies, migrations and tests.

Add RED tests for tenant scope, permissions, idempotency, durable outbox claims, retry/fencing, parking while disabled, audit, safe templates/recipients, and no-network behavior when dark. Validate migrations and full backend suite. Keep live delivery disabled.

## Task 20: Rebuild PR #71 — tenant email UI

After #70 merges, retarget a replacement to `main`. Use the accepted OpenAPI/client contract. Test tenant identity selection, compose validation, authorization, attachment/recipient limits if supported, parked/degraded states, retry display, and browser flows. No live email test is authorized.

## Task 21: Consolidate documentation PRs #39, #40, #47, and #72

**Files:** marketplace, Odoo, master-execution, contract, and n8n documentation/manifest files.

1. Inventory duplicate and conflicting authority statements.
2. Make current implementation documents authoritative and mark dated plans as historical.
3. Validate referenced paths, endpoints, capabilities, SHAs, owners, schemas, and integration direction.
4. Preserve the rule that Odoo and n8n communicate through Middleware boundaries rather than direct provider writes.
5. Merge one focused documentation PR, then close the four historical PRs with links.

## Task 22: Final repository certification and queue closure

**Files:** consolidation ledger, generated OpenAPI/contracts, release evidence only.

1. Confirm all 24 original PRs have final dispositions and links.
2. Confirm zero stacked PRs target unmerged feature branches.
3. Run complete backend, PostgreSQL/PostGIS, migration, frontend, E2E, contract, security, license, Docker/image, Compose, and orchestrator gates on final `main`.
4. Confirm one Alembic head, deterministic OpenAPI/client generation, zero unresolved review threads, and protected-main checks green.
5. Record exact final main SHA and evidence URLs.
6. Close only the remaining superseded/unsafe historical PRs whose unique changes are fully accounted for.
7. Report `GO` only for repository consolidation. Production deployment remains a separate gate.

## Stop conditions

Stop immediately and report `NO_GO` for the current slice if:

- the latest `main` cannot be fetched or the worktree is dirty unexpectedly;
- a PR's unique behavior cannot be distinguished from superseded code;
- a migration produces multiple heads or fails upgrade/check/drift/rollback policy;
- authorization, tenant scope, idempotency, concurrency, audit, or outbox behavior is unproven;
- required CI fails or is skipped unexpectedly;
- approval is stale or review threads remain;
- a fix requires ruleset weakening, alert dismissal, force-push, force-merge, secret exposure, or live-system mutation.

## Final handoff

The final report must contain the original 24 PRs, their disposition, replacement/merge PR, accepted SHA, exact tests/checks, reviewer state, and whether any capability changed. It must explicitly state that repository consolidation does not equal staging or production certification.
