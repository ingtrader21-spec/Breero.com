# BREERO Pull Request Consolidation Design

## Status and purpose

This specification defines how to reconcile the 25 pull requests that were open against `ingtrader21-spec/Breero.com` on 2026-09-19 without replaying stale history into the protected production baseline.

The goal is a small, auditable queue of current pull requests in which every surviving change is based on the latest accepted `main`, has one clear responsibility, passes the applicable repository gates, receives fresh exact-head review, and is merged before dependent work begins.

This is a source-control and code-quality mission. It does not authorize a deployment, production-data mutation, payment activation, live email, provider dispatch, automatic booking, Odoo writes, or external automation.

## Accepted baseline

The design was prepared from protected `main` commit:

```text
f76a397142c2b0da1f94b849ca67f468219d64a1
```

The baseline must be refreshed before each execution slice. CI, approval, mergeability, migration, and generated-contract evidence belongs only to the exact commit on which it ran.

## Problem statement

The open queue mixes several different conditions:

- clean branches that are blocked by governance rather than conflicts;
- branches with stale mergeability state because their base moved;
- stacked branches whose base is another unmerged feature branch;
- historical branches whose functionality may already exist on `main`;
- large reconciliation branches that could reintroduce superseded runtime behavior;
- approved branches whose approvals no longer apply after synchronization;
- documentation that may contradict the current implementation.

Treating all 25 as ordinary merge conflicts would hide these distinctions and create a high-risk integration event. The repository's `AGENTS.md` explicitly requires dependency-safe slices rather than a repository-wide fix-all change.

## Chosen strategy

Use clean replay and consolidation from current protected `main`.

For every original PR, compute its unique patch and classify it as one of:

1. **Merge candidate** — current, narrowly scoped, and independently testable.
2. **Replacement candidate** — contains valuable behavior, but its history or surrounding code is stale. Reimplement or cherry-pick only the unique behavior onto a fresh branch.
3. **Stacked dependency** — cannot be evaluated or merged until its declared parent lands.
4. **Superseded** — all material behavior is already present on `main` or a later accepted PR.
5. **Rejected/unsafe** — would restore retired behavior, bypass current safety gates, or combine unrelated domains.

Original PRs are never force-pushed merely to make GitHub display a green merge box. If a fresh replacement branch is required, the original PR receives evidence linking it to the replacement before it is closed.

## Alternatives rejected

### Rebase all 25 branches in place

This preserves historical PR URLs but repeatedly invalidates approvals, makes conflict resolutions hard to review, and can silently restore code removed by later security work.

### One integration mega-PR

This reduces the number of PRs but destroys domain isolation, makes failures difficult to attribute, and violates the repository rule requiring dependency-safe slices.

### Merge every currently clean PR first

GitHub mergeability does not prove semantic compatibility, current tests, or absence of supersession. Even clean branches require patch classification and exact-head evidence.

## Execution invariants

- Refresh `origin/main` before starting each slice.
- Use one isolated worktree and one branch per slice.
- Preserve FastAPI, async SQLAlchemy, PostgreSQL/PostGIS, Alembic, Redis/Celery, Next.js, pnpm, and Turborepo boundaries.
- Keep route handlers thin: router to authorization/dependency to domain service to repository to PostgreSQL.
- Add or preserve regression coverage before changing behavior.
- Keep the Alembic graph linear and verify upgrade, check, schema drift, and prior-head paths for migration-affecting work.
- Regenerate OpenAPI and frontend contracts only from the accepted runtime surface.
- Keep live capabilities dark unless a separate mission explicitly certifies activation.
- Never reuse approvals or CI results after a new commit, rebase, merge, or retarget.
- Merge one slice, verify protected `main`, then rebase the next slice on that accepted SHA.
- Do not close a historical PR until its unique patch has been classified and evidence is recorded.

## Consolidation waves

### Wave 0: inventory and provenance

Create a machine-readable ledger for PRs `#39, #40, #41, #47, #55, #58, #59, #60, #62, #65, #67, #69, #70, #71, #72, #100, #101, #102, #105, #109, #110, #115, #117, #123, #124`.

Each row records:

- PR and branch;
- head and base SHAs;
- changed files and owning domains;
- merge-base with current `main`;
- patch-id or equivalent unique-change evidence;
- current CI, review, threads, and mergeability;
- dependency and consumer relationships;
- capability, migration, OpenAPI, security, and deployment effects;
- classification and evidence-backed disposition.

Wave 0 makes no runtime changes and closes no PRs.

### Wave 1: foundation and release gates

Order:

1. `#41` backend bootstrap tooling.
2. `#124` documented `/ready` contract.
3. `#60` configuration boundaries.
4. `#65` read-only deployment preflight.

These changes establish the test and configuration substrate required by later slices. Each is rebuilt from the latest accepted `main` when its original history is stale.

### Wave 2: API boundaries and runtime safety

Order:

1. `#55` public submission, consent, rate-limit, and idempotency hardening.
2. `#58` operations resource boundaries.
3. `#59` jobs and work-request boundaries.
4. `#62` fail-closed endpoint ownership and policy registry.
5. `#105` worker connection isolation and tracing.

Structural refactors must preserve methods, paths, authorization, error envelopes, operation IDs, database behavior, and frontend consumers. Any behavioral fix receives a regression test that fails against the pre-fix tree.

### Wave 3: identity, dependency, and deployment reconciliation

- Compare `#100` with the later accepted dependency-security work. Close it as superseded if no unique safe patch remains; otherwise replay only the missing package-policy correction.
- Reconcile `#102` against the current Keycloak issuer, BFF ownership, and local-credential safety model.
- Rebuild the unique production-compose changes from `#101` on current `main`; preserve digest pinning, non-root execution, read-only filesystems, health checks, and dark capabilities.
- Treat `#123` as an evidence source, not a merge candidate. Its 132-file runtime promotion must be decomposed. Unique safe changes go through their owning wave; superseded or unsafe changes are documented and closed.

### Wave 4: portal backend and generated contracts

Order:

1. `#109` tenant-scoped provider, operations, and admin read models.
2. `#115` generated types and API client from the newly accepted canonical OpenAPI.
3. `#110` Keycloak BFF runtime for partner, operations, and admin portals.
4. `#69` role-aware interactions and access administration.

Authorization, tenant/legal-entity scope, PII minimization, server-side token handling, and negative access tests are mandatory. `#115` is retargeted to `main` only after `#109` merges and the OpenAPI artifact is regenerated.

### Wave 5: frontend visual authority

Evaluate `#67` and `#117` together because both claim broad UI authority.

Select one current shell and token system. Recover compatible components from the other branch only when they have a current consumer and pass accessibility, responsive, unit, contract, build, and browser tests. Do not merge two competing global shells or duplicate design-token authorities.

### Wave 6: email domain

Order:

1. `#70` tenant provisioning, compose commands, durable outbox, recovery, authorization, and audit.
2. `#71` compose and provisioning frontend after the backend contract lands.

Email transport remains disabled and parked by default. This wave does not certify Klyrow delivery or authorize live sending.

### Wave 7: documentation authority

Consolidate `#39`, `#40`, `#47`, and `#72` after their referenced runtime decisions are accepted.

Documentation must describe current code and named future work separately. Conflicting mission documents are replaced by one current authority plus dated historical evidence; documentation cannot claim production readiness or deployment without runtime proof.

## Per-slice development contract

Every replacement or repaired PR follows this sequence:

1. Record current `main`, original PR head, merge-base, worktree status, and affected contracts.
2. Identify the smallest unique behavior worth preserving.
3. Create a fresh branch from current `main` in an isolated worktree.
4. Write or select the regression test that proves the behavior.
5. For behavioral fixes, demonstrate RED on the pre-fix state.
6. Implement the smallest current-architecture change.
7. Run focused tests, then every applicable repository gate.
8. Inspect the full diff for stale files, generated artifacts, secrets, and unrelated changes.
9. Push and open or update one PR with exact-head evidence.
10. Obtain independent approval after the final push and resolve every review thread.
11. Merge only through protected controls.
12. Verify post-merge `main` and update the ledger before continuing.

## Required evidence by change type

### Backend/API

- Ruff, mypy, compile, unit and integration tests.
- PostgreSQL/PostGIS tests where persistence or geography is affected.
- Authorization, ownership, tenancy, validation, error, concurrency, idempotency, audit, and outbox coverage as applicable.
- Alembic upgrade/check/drift/prior-head evidence for schema work.
- Deterministic OpenAPI generation and frontend contract verification.

### Frontend

- Frozen pnpm installation.
- Dependency and license policy.
- Lint, typecheck, unit tests, contract check, production builds, and Playwright coverage for affected applications.
- Accessibility and responsive evidence for shared UI changes.

### CI/deployment

- Workflow syntax and permissions review.
- Read-only behavior for preflight jobs.
- Secret scan, dependency scan, image build, image vulnerability scan, and runtime metadata checks as applicable.
- No deployment from a cleanup PR.

### Documentation

- Link and referenced-path validation.
- Scope/classification checks.
- No stale SHAs represented as current state.
- No readiness claim without corresponding executable evidence.

## Failure and rollback behavior

- A failing required gate stops the current slice. Later waves do not start.
- A semantic conflict is resolved against current accepted architecture, not by mechanically choosing either side.
- A failed merge or post-merge check leaves dependent work paused and opens a focused repair branch.
- No force-push, force-merge, history rewrite, approval bypass, alert dismissal, or ruleset weakening is authorized.
- Runtime rollback follows the owning PR's migration and capability plan; documentation-only and refactor-only slices use ordinary revert when safe.

## Completion criteria

The consolidation mission is complete only when:

- all 25 original PRs have an evidence-backed disposition;
- every preserved change is merged through a current, green, independently reviewed slice;
- superseded and rejected PRs link to their replacement or accepted evidence before closure;
- no stacked PR targets an unmerged feature branch;
- no unresolved review threads remain;
- current `main` passes required backend, frontend, contract, security, and orchestration gates;
- migrations have one head and OpenAPI/contracts are deterministic;
- production capabilities remain in their explicitly certified states;
- a final ledger records original PR, replacement PR or accepted merge, final SHA, tests, review, and disposition.

## Explicit non-goals

- Deploying to staging or production.
- Enabling payments, payouts, automatic scheduling, provider dispatch, email, SMS, callbacks, or Odoo writes.
- Preserving obsolete branch history for its own sake.
- Combining unrelated domains merely to reduce the PR count.
- Declaring the wider BREERO product production-ready from repository cleanup evidence alone.
