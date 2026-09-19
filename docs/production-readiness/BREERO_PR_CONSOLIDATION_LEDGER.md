# BREERO pull-request consolidation ledger

Status date: 2026-09-19

Canonical baseline: `main@93d72d032d8a382e15f0869f51dc42b7722926d9`

Scope: the 24 pull requests left open after PR #124 merged

Deployment status: **no deployment performed or authorized**

This ledger is the merge-control record for the mission recovery. Every pull
request is represented exactly once in the machine-readable ledger at
`artifacts/pr-consolidation/ledger.v1.json`. A disposition is not permission to
merge: every candidate or replacement must still be rebuilt on current `main`,
tested at its exact head, approved after its final material change, and pass all
protected checks.

## Disposition definitions

- `candidate`: narrow enough to revalidate at its current head before deciding
  whether to replace or merge.
- `replacement_required`: useful intent exists, but the historical branch must
  not merge directly; recover it in a current, scoped replacement.
- `stacked`: depends on a parent contract that must land first.
- `superseded`: a later pull request owns the same outcome; compare and close
  only after proving no unique requirement was lost.
- `unsafe`: never merge wholesale; decompose at file and behavior level.

## Current classification

| PR | Domain | Disposition | Gate or dependency |
|---:|---|---|---|
| #39 | Marketplace authority docs | replacement required | Reconcile after runtime decisions |
| #40 | Odoo authority docs | replacement required | Preserve Middleware-only boundary |
| #41 | Bootstrap tooling | candidate | Exact-head safety tests |
| #47 | Mission architecture docs | replacement required | Produce one current authority |
| #55 | Public submissions | replacement required | Replay with consent, PII, and idempotency proof |
| #58 | Operations API | candidate | Depends on accepted #55 behavior |
| #59 | Jobs API | candidate | Follows #58 route boundary |
| #60 | Configuration | candidate | Preserve public Settings behavior |
| #62 | Endpoint policy | replacement required | Regenerate after #58, #59, and #60 |
| #65 | Deployment preflight | replacement required | Read-only validation only |
| #67 | Design system | replacement required | Competes with #117; select one shell |
| #69 | Portal UX | replacement required | Depends on #109, #110, and #115 |
| #70 | Email backend | replacement required | Rebuild on current worker/auth foundations |
| #71 | Email UI | stacked | Blocked on replacement #70 contract |
| #72 | Integration docs | replacement required | Align to final Middleware boundary |
| #100 | Dependency security | superseded | Compare with PR #134 before closure |
| #101 | Production Compose | replacement required | No deployment; validate one authority |
| #102 | Identity security | candidate | Current negative auth tests required |
| #105 | Worker runtime | candidate | Exact-head lifecycle and tracing tests |
| #109 | Portal backend | replacement required | Decompose mixed-domain patch |
| #110 | Portal BFF | replacement required | Depends on #102, #109, and #115 |
| #115 | Generated types | stacked | Regenerate from accepted OpenAPI |
| #117 | Horizon shell | replacement required | Competes with #67; select one shell |
| #123 | Cross-domain runtime | unsafe | Decompose; never merge the 132-file branch wholesale |

## Controlled execution order

1. Establish this ledger and its CI validator.
2. Recover foundations: #41, #60, #65, #55, #58, #59, #62, and #105.
3. Dispose of #100 only after comparison with #134.
4. Recover identity and deployment: #102 and #101.
5. Decompose #123 and recover portal contracts: #109, #115, #110, and #69.
6. Select one UI authority from #67 and #117.
7. Recover email backend/UI: #70 then #71.
8. Consolidate documentation from #39, #40, #47, and #72.
9. Run final exact-head certification and close only branches whose intent is
   merged, superseded, or explicitly rejected with evidence.

## Non-negotiable merge gates

- Branch is based on the then-current protected `main`.
- Scope and dependency claims match this ledger or an approved ledger update.
- Required tests and security scans pass at the exact reviewed head SHA.
- Approval is fresh after the last material change.
- GitHub protected checks and license-policy criteria pass.
- Merge uses the repository's protected flow; no bypass or force push.
- Deployment remains a separate, explicitly authorized operation.
