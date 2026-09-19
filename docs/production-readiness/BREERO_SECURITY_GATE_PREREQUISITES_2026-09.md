# BREERO security-gate prerequisites - September 2026

Status: prerequisite candidate; protected merge and post-merge verification pending. This is not a certified baseline.

The user explicitly authorized a separate prerequisite PR for the transferred-repository identity failure and portal runtime npm vulnerabilities, as an exception to the original two-PR sequence. Security PR #134 remains separate. Foundation recovery still requires its complete security gate to pass.

## Identity and trust repair

Canonical GitHub repository is `ingtrader21-spec/Breero.com`, stable repository ID `1331354808`; base main is `2292fd7533faa5752a3df7a8243e217447694367`. The contract and both validators used the former owner in thirteen active identity/catalog bindings, causing the required orchestrator check to reject the actual GitHub repository.

The repair changes those active bindings and the corresponding self-test lookup. It preserves the stable ID, roles, authority flags, required checks, independent-review policy, disabled live effects, and existing GHCR image namespaces. Registry migration is not inferred from a GitHub repository transfer. Historical references and unrelated integration metadata are outside this repair.

BREERO receives its own production-validator digest and normalized release-policy fingerprint. The explicit normalization list includes only the new static digest binding, preventing a digest cycle while retaining validation for missing, duplicate and executable binding values. Every other repository's trust maps and fingerprints were compared against base and remain unchanged.

The portal Dockerfile's executable digest is refreshed because its runtime packaging changes. BREERO's full source-closure digest is recomputed last from the staged tree; the release validator itself remains the existing excluded self-reference. No check is bypassed or reduced.

## Runtime packaging repair

The unchanged portal runtime previously retained npm 10.9.8 from `node:22-alpine`. Image scans located one critical and ten high findings per image in `/usr/local/lib/node_modules/npm/node_modules/`, including critical `tar@7.5.11`. These packages were outside the pnpm application graph.

The portal runtime now follows the existing web image pattern: remove unused npm and npm/npx launchers before creating the existing non-root user. Build-stage pnpm, application dependencies, entrypoints and health checks are preserved. Corepack remains; its old Vitest dev-dependency metadata is not an installed Vitest package. No unrelated package upgrade was added.

| Image | Before critical/high | After critical/high | Runtime check |
|---|---|---|---|
| Admin | 1 / 10 | 0 / 0 | npm absent, UID10001, health OK |
| Operations | 1 / 10 | 0 / 0 | npm absent, UID10001, health OK |
| Partner | 1 / 10 | 0 / 0 | npm absent, UID10001, health OK |

Local application builds used a validation copy of the candidate Dockerfile with only the application build RUN restricted to `--network=none`. Runtime probes also used `--network=none`, published no ports, queried only localhost, and stopped their own containers afterwards. No deployed server or live provider was contacted. Trivy scans used no suppression file and did not ignore unfixed findings.

## Regression evidence

- Canonical identity acceptance failed before the repair. Positive validation now passes alongside rejection of the former owner, an unregistered owner, mismatched contract identity, wrong contract ID and wrong event ID.
- Missing, duplicate and nonliteral BREERO trust bindings are rejected, alongside the existing shared-binding injection, authority, supply-chain, workflow mutation and review-policy regressions.
- The changed portal Dockerfile initially failed its pinned executable check. Its actual bytes now pass, while modified bytes are rejected.
- Runtime package-manager absence probes failed for all three previous images and pass for all repaired images; health checks pass as the existing non-root user.
- The complete production validator and release-intent self-test pass in Linux with Python3.12 and PyYAML6.0.3, networking disabled and an explicit dummy test token.
- A Windows run encountered an existing Linux-path negative fixture; validation therefore uses Linux. Git archive must use per-command `core.autocrlf=false` so byte-bound inputs match Git blobs; no shared Git configuration was changed.

[Machine-readable evidence](../../artifacts/security-remediation/prerequisites.json) records development snapshot, commands, exits, image digests, scan results and trust-isolation checks. Local SPDX/SLSA attestations remain unsigned development evidence, not approved release provenance. Exact final-head CI and GitHub approval must be checked separately before merge.

This prerequisite does not resolve the eight main-branch Dependabot alerts; PR #134 must follow with current checks, independent approval, protected merge and post-merge alert verification. Complete SAST/license-policy and signed baseline requirements from the original mission remain in force. No foundation claim or reconciliation authorization is made here.

`PRODUCTION_ACTIVATED=NO`. `LIVE_PROVIDER_CALLS=NO`. `PR_RECONCILIATION_AUTHORIZED=NO`.
