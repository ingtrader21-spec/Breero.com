# BREERO critical dependency remediation - September 2026

`SECURITY_GATE=FAIL`. `MERGE_GATE=BLOCKED`. No certified baseline exists.

[Security PR #134](https://github.com/ingtrader21-spec/Breero.com/pull/134) aligns all eight direct Vitest declarations with the already-patched workspace resolution. Implementation evidence below belongs to immutable source `5b833933c18ebcaa380fc3988cf9efe219c43642`. This report is an evidence-only follow-up: its commit requires fresh protected checks and approval. Historical results are not post-merge certification.

Canonical repository: `ingtrader21-spec/Breero.com`, stable repository ID `1331354808`. `SECURITY_BASE_SHA=2292fd7533faa5752a3df7a8243e217447694367`. Main remains at that SHA. The two original real worktrees remain clean and unchanged. The preserved 784-file source snapshot has SHA-256 `75a07a373efde098cb08035ad03628608da9117bfaee3885da25b282a4e080ee`.

## Dependency change and historical before-state

[GHSA-5xrq-8626-4rwp](https://github.com/advisories/GHSA-5xrq-8626-4rwp) is patched at Vitest 3.2.6 on the selected release line. Before this change, root `pnpm.overrides.vitest=3.2.6` and the single authoritative `pnpm-lock.yaml` already resolved every workspace to 3.2.6, but eight direct manifests still declared `^2.1.8`.

| Dependabot alert | Manifest | Before declaration | After declaration | Resolution before/after |
|---|---|---|---|---|
| #1 | `apps/admin/package.json` | `^2.1.8` | `3.2.6` | `3.2.6` |
| #2 | `apps/ops/package.json` | `^2.1.8` | `3.2.6` | `3.2.6` |
| #3 | `apps/partner/package.json` | `^2.1.8` | `3.2.6` | `3.2.6` |
| #4 | `apps/web/package.json` | `^2.1.8` | `3.2.6` | `3.2.6` |
| #5 | `packages/api-client/package.json` | `^2.1.8` | `3.2.6` | `3.2.6` |
| #6 | `packages/portal/package.json` | `^2.1.8` | `3.2.6` | `3.2.6` |
| #7 | `packages/types/package.json` | `^2.1.8` | `3.2.6` | `3.2.6` |
| #8 | `packages/ui/package.json` | `^2.1.8` | `3.2.6` | `3.2.6` |

No runtime major-version transition occurred. Vite remains 6.4.3. Matching `@vitest/coverage-v8@3.2.6` was added as root test tooling because coverage had no provider. Independent lockfile comparison found no existing package/snapshot version changed or removed; 42 coverage-related entries were added. Per-workspace dependency trees and commands are in [preflight.json](../../artifacts/security-remediation/preflight.json) and [result.json](../../artifacts/security-remediation/result.json).

The declaration guard failed with eight violations before remediation and passed with zero afterwards. Three characterization tests passed before the manifest changes: deferred profile loading with alias/setup/DOM behavior, disabled/enabled React button interaction, and the API client's 150 ms retry with fake-timer cleanup. Test configuration and application implementation remain unchanged.

## Validation at implementation source 5b83393

| Check | Evidence/result |
|---|---|
| Clean frozen install | pnpm 10.0.0, Node 22.23.2, new empty store, exit 0; lockfile unchanged |
| Lint and typecheck | Exit 0 across all applicable workspace tasks |
| Unit tests | 61 before characterization; 64 afterwards: web 35, UI 9, API client 18, types 2 |
| Coverage | Same 64 tests pass with the matching V8 provider; no global coverage threshold is configured |
| Empty suites | Admin, ops, partner and portal have no test files and retain existing `passWithNoTests`; no workflow certification follows |
| Frontend contract | Exit 0; 30 required paths; zero forbidden payment mutations |
| Build | Windows standalone copy failed with symlink `EPERM`; Linux CI full workspace build passed |
| Browser tests | 255 passed across Chromium, Firefox and WebKit |
| Workspace dependency audit | `pnpm audit --audit-level high` exits 0; zero critical/high and three moderate package findings |
| Secret scan | Pinned Trivy source scan exits 0, zero matches |
| SAST | Pinned Semgrep `p/security-audit` exits 0, zero findings, but five partial-parsing warnings; complete SAST gate remains BLOCKED |
| License inventory | `pnpm licenses list --json` exits 0; no approved license policy found, so policy gate remains BLOCKED |
| Local image builds | Web, admin, ops and partner all build successfully; none was started or published |
| Image security | Web scan: zero critical/high. Each portal image: one critical and ten high; container gate FAIL |
| SBOM/provenance | Local SPDX and SLSA attestations extracted and bound to image digests; unsigned local records are not approved signed release provenance |

[Linux quality run 35452423086](https://github.com/ingtrader21-spec/Breero.com/actions/runs/35452423086) passed on implementation source `5b83393`. Full command, exit, digest, dependency, image, finding, review and check records are in `result.json`. The JSON audit command returned 1 while reporting the three moderate findings; the exact CI threshold command separately returned 0. No audit result was suppressed.

Portal build validation used external Dockerfile copies adding only `RUN --network=none` to the application build command. The web's offline attempt failed on Google Fonts. Its successful build used the unchanged tracked Dockerfile with live API, staging API, Keycloak and telemetry hostnames mapped to loopback; independent static inspection found no provider build-time path. Google Fonts downloads remained available. No runtime image, live provider, deployment, or release publishing workflow was invoked.

## Blocking findings

1. **Protected repository identity.** [Required orchestrator check](https://github.com/ingtrader21-spec/Breero.com/actions/runs/35452422959/job/105921777227) fails with `repository is outside the protected catalog identity map`. The unchanged validator still identifies `appolon1908-hue/Breero.com` at `.codestra/validate-production-orchestrator-contract.py:368,6585`; the contract and release trust maps also retain the former owner. This predates the dependency change and failed on the preflight-only commit. Repair requires coordinated identity-policy work; spoofing the old name or weakening the check is not acceptable.
2. **Bundled npm vulnerabilities.** Each newly built admin, ops and partner image contains npm 10.9.8 from `node:22-alpine`, with one critical and ten high findings under `/usr/local/lib/node_modules/npm/node_modules/`. The critical finding is `tar@7.5.11`, `CVE-2026-59873`; other findings affect tar, brace-expansion, ip-address, pacote, picomatch and sigstore. Exact scanner identifiers, paths and proposed fixed versions are in `result.json`. These packages are outside the workspace lockfile. `deploy/portals/Dockerfile` is unchanged (blob `5460e62d4832df1e00a745d6f331c1d836846ba5`). The current Node base is `sha256:b6f26b36c8ff49624cfdac716b8ea1138d606df02586a77d364bb5536a634f85`. A mutable base means this does not establish the versions in an older deployed image.
3. **Incomplete policy evidence.** SAST has five partial-parsing warnings; no approved complete SAST or license-policy command was found. Repository-approved signed provenance uses a main-only publishing workflow and was not invoked. None of these gaps is reported as PASS.

All four final image filesystems were inspected with OCI whiteout handling. Application Vitest declarations are patched; no installed Vitest package was found. Bundled Corepack/npm dev-dependency metadata still contains older Vitest declarations. These are explicitly recorded, not mistaken for installed vulnerable runtime packages. Next's bundled tar/picomatch copies have UNKNOWN SBOM versions, so their absence from version-specific findings is not a vulnerability-free certification.

The mission excludes unrelated upgrades and mixing portal/configuration changes into this PR. No such fixes or alert suppressions were made. Completing the gate requires separately authorized ownership-policy and runtime-toolchain remediation, plus resolved policy evidence.

## Review, merge and downstream status

A fresh independent code review found no source/test/dependency defects and retained incomplete validation as a merge blocker. GitHub owner `ingtrader21-spec` approved implementation source `5b83393` at `2026-09-19T15:39:09Z`; an evidence-only push still requires approval/check refresh under branch policy. The agent review is not a substitute for GitHub approval.

Main requires current `quality` and `orchestrator-contract`, one independent approval including the latest push, resolved threads and squash merge. No merge was attempted with failing gates. Dependabot remains at **8 critical, 0 high and 11 medium open alert instances on main**. Alerts #1-#8 have not been dismissed or resolved by a merge. The 11 medium instances include Vitest/mocker GHSA-82fw-gwwq-j7x9 and PostCSS GHSA-fxqj-rqcc-2cmp; three unique moderate package findings in pnpm are a different counting unit.

- [x] Refresh and map all eight critical alerts; create and push PR #134.
- [x] Characterize existing behavior before changing declarations.
- [x] Pin all eight declarations, add matching coverage tooling, regenerate the lockfile and run candidate checks.
- [ ] Pass the full security gate, including container and policy requirements.
- [ ] Obtain fresh required checks and independent approval; merge through protection.
- [ ] Verify exact post-merge main checks and alert resolution.
- [ ] Start foundation recovery only after the security gate passes.

Tasks 1 and 2 are implemented but not complete under the user's merged/post-merge definition. Task 3 is blocked by validation; Task 4 is blocked; Tasks 5-8 have not started. No foundation source claim, migration certification, signed baseline or 34-PR reconciliation authorization is made. Rulings and preservation evidence are recorded in `result.json`.

`SECURITY_MERGE_SHA=NONE`. `CERTIFIED_BASE_SHA=NONE`. `PR_RECONCILIATION_AUTHORIZED=NO`. `PRODUCTION_ACTIVATED=NO`. `LIVE_PROVIDER_CALLS=NO`. No capability default changed.
