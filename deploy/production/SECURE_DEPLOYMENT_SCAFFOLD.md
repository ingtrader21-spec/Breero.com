# BREERO secure deployment scaffold

## Status

```text
SCAFFOLD_ONLY=YES
LIVE_SERVER_CHANGED=NO
RUNTIME_PATHS_VERIFIED=NO
DEPLOYMENT_AUTHORIZED=NO
PRODUCTION_READY=NO
```

This package validates deployment files in GitHub Actions and provides a read-only host verifier. It does not connect to a server, use deployment credentials, create or restart containers, run migrations, reload Caddy, change DNS, write secrets, or activate a capability.

## Current Compose authority

The repository presently contains two backend production definitions:

```text
docker-compose.production.yml
deploy/production/docker-compose.backend.yml
```

`docker-compose.production.yml` is the **review candidate** because it includes:

- one-shot migration profile;
- API, worker and scheduler;
- PostgreSQL/PostGIS and Redis;
- internal application network and externally provisioned Caddy network;
- read-only filesystems, dropped capabilities and no-new-privileges;
- resource/PID limits, bounded logs and file-backed secrets;
- API, PostgreSQL and Redis healthchecks;
- immutable digest requirements.

`deploy/production/docker-compose.backend.yml` remains an inventory/compatibility file only until an explicit migration or retirement PR is reviewed. It must not be operated beside the candidate against the same volumes. It currently omits the scheduler and disables the worker healthcheck, so it is not silently treated as equivalent.

The frontend candidate is:

```text
deploy/frontend/docker-compose.frontend.yml
```

The frontend Dockerfile on current `main` still contains the retired `auth.codestra.agency` issuer. PR #46 contains the canonical `https://auth.codestra.co/realms/codestra` repair and must be independently reviewed and merged before a frontend production image is certified. This scaffold does not hide, duplicate or prematurely merge that repair.

A candidate path is not runtime authority. Runtime authority exists only after the read-only host evidence below passes and the exact Git SHA, hashes, network names, Caddy routes and image digests are independently reviewed.

## CI-only validation

`.github/workflows/deployment-preflight.yml`:

- uses `contents: read` only;
- pins every external action to an exact commit;
- disables persisted checkout credentials;
- receives no SSH key, registry write token or production environment;
- never uses `pull_request_target`;
- renders Compose with temporary non-secret fixtures;
- rejects mutable application image tags;
- rejects published host ports, privileged mode, host namespaces, device mappings and Docker socket mounts;
- requires the expected private/edge networks, healthchecks, hardening controls and file-backed secrets;
- verifies application secret mounts plus PostgreSQL password-file and Redis ACL-file consumption;
- validates the read-only runtime verifier and path-classification tests;
- records that the live server remains unchanged.

The preflight intentionally warns rather than certifies worker and scheduler liveness because the current candidate does not yet define a healthcheck/heartbeat proof for those processes. That evidence is a production blocker, not something CI should invent.

## Read-only runtime verification

The operator must gather the actual values from the approved host without modifying it and pass them to:

```bash
scripts/deploy/verify-runtime-paths.sh \
  --config - \
  --mode host-read-only <<'EOF'
VERIFICATION_STATE=READY_FOR_READ_ONLY_VERIFICATION
LIVE_MUTATION_ALLOWED=false
# Supply every remaining key from runtime-paths.example.env using the actual,
# independently checked host paths, SHA values, image digests and networks.
EOF
```

The verifier never sources the input. It allowlists every key and rejects duplicate or unknown fields. In host-read-only mode it checks:

- approved hostname;
- exact clean Git checkout SHA;
- repository-contained backend, frontend and legacy Compose paths after real-path resolution;
- absolute readable repository, Caddy and environment paths;
- exact SHA-256 values for the candidate backend/frontend Compose and Caddy configuration;
- non-world-readable environment files;
- successful migration-profile and frontend `docker compose config --quiet` rendering;
- every rendered file-backed secret path exists, is readable and is not world-accessible;
- exact immutable API and frontend image digests in rendered Compose;
- existing internal private network and approved external edge networks;
- valid/adaptable Caddy configuration containing the expected web/API hosts and upstreams;
- absence of non-loopback listeners on ports 3000, 8000, 5432 and 6379.

It does **not** run `docker compose up/down/pull/run/exec`, migrations, SSH/SCP/rsync, package installation, Caddy reload, `systemctl`, or filesystem mutation commands.

A passing command produces evidence on standard output only:

```text
RUNTIME_PATHS_VERIFIED=YES
LIVE_SERVER_CHANGED=NO
```

Capture that output in the protected change record. Do not change `LIVE_MUTATION_ALLOWED` to true; a separately reviewed deployment workflow and approval are required after verification.

## Required sequence before any live action

```text
1. Merge and verify the required path-aware `quality` gate.
2. Resolve every stacked-branch conflict against exact current bases.
3. Obtain independent review and protected merges in dependency order.
4. Merge the canonical frontend issuer repair from PR #46.
5. Select/retire the competing Compose authority through review.
6. Complete worker and scheduler heartbeat/health evidence.
7. Build API/frontend once in trusted CI and publish immutable digests with SBOM, provenance and scan evidence.
8. Run the read-only runtime-path verifier on the approved host.
9. Prove current DNS, TLS, Caddy routes, private networks, disk/capacity and public-port posture.
10. Create and restore a dated backup in an isolated target.
11. Deploy the exact candidate digests to isolated staging.
12. Pass browser/API/UAT, migration, restart, recovery and rollback tests.
13. Use a separate protected production change with a canary and abort thresholds.
```

## Mandatory unresolved gates

```text
FRONTEND_KEYCLOAK_ISSUER=BLOCKED_BY_PR_46
CANONICAL_PRODUCTION_COMPOSE=CANDIDATE_NOT_CERTIFIED
WORKER_HEALTHCHECK=UNVERIFIED
SCHEDULER_HEALTHCHECK=UNVERIFIED
RUNTIME_HOST_PATHS=UNVERIFIED
CADDY_RUNTIME_ROUTES=UNVERIFIED
DNS_TLS=UNVERIFIED
BACKUP_RESTORE=UNVERIFIED
ISOLATED_STAGING=UNVERIFIED
PRODUCTION_DEPLOYMENT=NOT_PERFORMED
```

Payments, payouts, paid leads, instant/automatic booking, automatic assignment/confirmation, provider self-service, matching, messaging, reviews, marketing, unrestricted email/SMS, Odoo writes and external automation remain disabled unless their separate implementation and activation gates pass.
