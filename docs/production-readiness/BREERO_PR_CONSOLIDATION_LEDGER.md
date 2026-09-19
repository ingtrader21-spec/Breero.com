# BREERO historical PR consolidation ledger

The machine-readable record is [ledger.v1.json](../../artifacts/pr-consolidation/ledger.v1.json).
Its initial baseline is protected main `93d72d032d8a382e15f0869f51dc42b7722926d9`.
The baseline's [quality](https://github.com/ingtrader21-spec/Breero.com/actions/runs/35462147559)
and [orchestrator](https://github.com/ingtrader21-spec/Breero.com/actions/runs/35462147489)
checks succeeded. This records 24 historical PRs; it does not accept their behavior.

The user-supplied 2026-09-19 implementation plan governs the task order below.
Its named design specification,
`docs/superpowers/specs/2026-09-19-breero-pr-consolidation-design.md`, was unavailable
in fetched history and the known local clones when this ledger was prepared.
The schema and classifications are provisional pending that document. No claim
is made that the missing specification was read or approved by this change.

## Reading the evidence

Every row preserves the captured PR head, the base reported by GitHub, the local
merge-base against the stated main, changed files, checks, reviews and unresolved
thread URLs. GitHub's reported base can lag main; it is deliberately distinct from
the current baseline and merge-base. The capture contains 482 changed-file records,
189 checks and 206 reviews. Twelve PRs have unresolved threads, totaling 39.

`dependencies` records prerequisites declared or ordered by the supplied plan.
An empty list is not proof of semantic independence; each row states that limit.
`replacement_pr` and `accepted_sha` remain null until a later task provides
evidence. `captured_not_accepted` means retrieval succeeded, including failed
historical checks and stale reviews. It never means that the PR is ready to merge.
Final head-stability rechecks absent from a source capture remain explicitly unknown.

Disposition meanings:

- `candidate`: retain for a focused comparison against refreshed main.
- `replacement_required`: preserve any unique accepted behavior through a focused replacement.
- `stacked`: a historical feature-branch base requires accepted prerequisites and regeneration or replay.
- `superseded`: use only after every unique change is accounted for by accepted main evidence.
- `unsafe`: use only with specific evidence identifying prohibited or obsolete behavior and accounting for any safe unique changes.

No initial row is labeled superseded or unsafe. Broad or failing historical work
still requires decomposition; neither fact alone justifies discarding unique logic.

## Initial dispositions and task order

All rows below have evidence status **captured, not accepted**. No replacement or
accepted SHA is assigned, and no capability changes in this task.

| Original PR | Domain | Initial disposition | Planned task / prerequisite |
| --- | --- | --- | --- |
| [39](https://github.com/ingtrader21-spec/Breero.com/pull/39) | Marketplace authority | replacement_required | 21: shared authority documentation |
| [40](https://github.com/ingtrader21-spec/Breero.com/pull/40) | Odoo governance | replacement_required | 21: shared authority documentation |
| [41](https://github.com/ingtrader21-spec/Breero.com/pull/41) | Backend bootstrap | replacement_required | 2: fail-closed tooling |
| [47](https://github.com/ingtrader21-spec/Breero.com/pull/47) | Execution/architecture authority | replacement_required | 21: shared authority documentation |
| [55](https://github.com/ingtrader21-spec/Breero.com/pull/55) | Public submissions | replacement_required | 5: persisted intake contracts |
| [58](https://github.com/ingtrader21-spec/Breero.com/pull/58) | Operations API | candidate | 6: after accepted #55; preserve routes and behavior |
| [59](https://github.com/ingtrader21-spec/Breero.com/pull/59) | Jobs API | replacement_required | 7: after accepted #55; separate dependency delta |
| [60](https://github.com/ingtrader21-spec/Breero.com/pull/60) | Settings | candidate | 3: preserve configuration contract |
| [62](https://github.com/ingtrader21-spec/Breero.com/pull/62) | Endpoint registry | replacement_required | 8: after accepted #55; fail-closed route ownership |
| [65](https://github.com/ingtrader21-spec/Breero.com/pull/65) | Deployment preflight | replacement_required | 4: read-only validation |
| [67](https://github.com/ingtrader21-spec/Breero.com/pull/67) | Shared UI shell | replacement_required | 18: one replacement with #117 |
| [69](https://github.com/ingtrader21-spec/Breero.com/pull/69) | Portal dashboards | replacement_required | 17: accepted #109/#115/#110 contracts |
| [70](https://github.com/ingtrader21-spec/Breero.com/pull/70) | Tenant email/outbox | replacement_required | 19: delivery stays disabled |
| [71](https://github.com/ingtrader21-spec/Breero.com/pull/71) | Tenant email UI | stacked | 20: accepted #70 |
| [72](https://github.com/ingtrader21-spec/Breero.com/pull/72) | n8n governance | replacement_required | 21: shared authority documentation |
| [100](https://github.com/ingtrader21-spec/Breero.com/pull/100) | Dependency security | candidate | 10: compare every manifest/lockfile delta |
| [101](https://github.com/ingtrader21-spec/Breero.com/pull/101) | Compose/scheduler | candidate | 12: current-safe topology |
| [102](https://github.com/ingtrader21-spec/Breero.com/pull/102) | Identity tests/docs | candidate | 11: current Keycloak/local-mode contract |
| [105](https://github.com/ingtrader21-spec/Breero.com/pull/105) | Worker database lifecycle | candidate | 9: per-process engine isolation |
| [109](https://github.com/ingtrader21-spec/Breero.com/pull/109) | Portal read models | replacement_required | 14: scope and persistence proof |
| [110](https://github.com/ingtrader21-spec/Breero.com/pull/110) | Portal BFF/session | replacement_required | 16: accepted backend/client contracts |
| [115](https://github.com/ingtrader21-spec/Breero.com/pull/115) | Generated client | stacked | 15: regenerate after #109 |
| [117](https://github.com/ingtrader21-spec/Breero.com/pull/117) | UI shell/session overlap | replacement_required | 18: one replacement with #67 |
| [123](https://github.com/ingtrader21-spec/Breero.com/pull/123) | Broad runtime branch | replacement_required | 13: map all 132 files; never integrate wholesale |

#100 overlaps the accepted Vitest remediation in #134, but includes a distinct
PostCSS override (`8.5.26` versus baseline `8.5.18`). #59 also includes that
dependency delta. Neither PR can be declared fully superseded from its title.
#71's recorded base is an older ancestor of the captured #70 head. #115 targets
the portal read-model branch; its generated artifacts must be regenerated later.

## Validation and advancement

Run from any directory, using absolute paths if necessary:

```bash
python scripts/pr_consolidation/validate_ledger.py
python -m unittest discover -s scripts/pr_consolidation -p 'test_*.py'
```

The validator uses only Python's standard library and local JSON. It rejects
missing/duplicate PRs, ambiguous dispositions, absent identity/ownership/contract
fields, invalid or cyclic dependencies, mismatched check heads, truncated captures
and malformed JSON. It performs no network access or repository mutation.
Successful validation proves structural completeness. It does not independently
verify GitHub assertions, semantic equivalence, fresh approval or merge eligibility.

For each later task, create a new worktree from refreshed protected main, preserve
the original captures, add current evidence and update the affected disposition.
Obtain exact-head green checks and fresh independent approval, merge through
protection, then verify post-merge main before starting another task. Never batch
historical merges or reuse stale checks. Add accepted PR/SHA and linked acceptance
records only after the user-required gates have actually passed.

Task 1 modifies no historical PR and closes none. Its CI integration runs the
validator and tests in the existing always-applicable scope/docs job. Existing
workflow/executable digest bindings and the source-closure digest must be updated
together; no runtime authority or protection is relaxed. The initial main's
source-closure pin and three executable pins (release-image workflow, API Dockerfile
and web Dockerfile) were already stale despite its successful self-test. Their
bindings are refreshed to unchanged protected-main source bytes. Actual final-tree
equality and every executable byte binding must be checked separately.

The referenced design specification and approved dependency-license policy were
unavailable at preparation. License inventory alone cannot satisfy the plan's
license-policy gate. These limitations must remain visible until resolved.

Repository consolidation does not equal staging or production deployment
readiness. Payments, assignments, confirmations, live dispatch, email/SMS,
callbacks, Odoo writes and external automation remain outside this task.
