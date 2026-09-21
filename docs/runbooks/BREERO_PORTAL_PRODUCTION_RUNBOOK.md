# BREERO portal production runbook

This runbook governs `breero.com`, `partners.breero.com`, `ops.breero.com`, and `admin.breero.com`. It does not authorize live payments, payouts, automatic provider assignment, email, SMS, or Middleware delivery.

## Authority boundaries

| Authority | Repository or system | Responsibility |
|---|---|---|
| Application | `appolon1908-hue/Breero.com` | Portal code, BFF, API, immutable image definitions, release manifest, health checks |
| Public edge | `appolon1908-hue/Caddy` | DNS hostname routing, HTTPS, certificates, HSTS, edge access logs |
| API gateway | `appolon1908-hue/Kong` | Private BFF-to-API route, OIDC bearer enforcement, audience, limits, correlation IDs |
| Identity | `appolon1908-hue/Keycloak` | Realm, confidential clients, redirect/logout URIs, service and portal roles |
| Secrets | OpenBao | Render distinct client/session secrets into root-owned files; no secret values in GitHub or Compose |
| Downstream integration | BREERO API → durable outbox → Middleware | Controlled Odoo/n8n/provider delivery after a separate capability approval |
| Observability | Prometheus, OpenTelemetry, Alloy, Loki, Tempo, Grafana | Private metrics, traces, structured logs, alerts, dashboards |

The BREERO repository must never apply Caddy or Kong configuration. It ships reviewed handoff contracts under `deploy/edge` and `deploy/gateway`.

## Required Keycloak clients

Create separate confidential clients. Do not share client secrets or session secrets between portals.

| Client | Exact production redirect URI | Exact production logout URI | Allowed application roles |
|---|---|---|---|
| `breero-partner` | `https://partners.breero.com/api/auth/callback` | `https://partners.breero.com/login` | `vendor_admin` |
| `breero-operations` | `https://ops.breero.com/api/auth/callback` | `https://ops.breero.com/login` | `operations`, `ops_manager`, `admin`, `superadmin` |
| `breero-administration` | `https://admin.breero.com/api/auth/callback` | `https://admin.breero.com/login` | `finance`, `admin`, `superadmin` |

Use Authorization Code, PKCE S256, standard OIDC scopes, short access-token lifetime, bounded refresh lifetime, exact web origins, exact redirect/logout URIs, and `breero-api` audience. Disable Direct Access Grants and implicit flow. Map the stable Keycloak subject to the BREERO user shadow; never authorize by email alone.

## Hard blockers

No staging or production apply may run while any of these GitHub issues is open:

- #17 — production host disk capacity
- #18 — staging environment unavailable
- #19 — schema and migration drift

The deploy workflow enforces these blockers only when `apply=true`, so dry-run release planning remains possible.

## Mandatory fail-closed state

Before staging certification and again before production apply, `GET /api/v1/portal/capabilities` must report all of the following as `false`:

```text
online_payments
payouts
automatic_assignment
middleware_delivery
```

Transactional email and SMS must remain disabled unless separately approved. The portal interface is not an authority to change these values.

## Source and artifact gate

1. Merge or otherwise assemble the reviewed backend contract, secure runtime, partner workspace, operations workspace, administration workspace, observability, and release-layer commits into one candidate Git commit.
2. Require the full protected-branch check suite at that exact 40-character commit.
3. Require an accepted GitHub-verified signature if the branch ruleset mandates signed commits.
4. Build all four images from that exact commit using `deploy/frontend/Dockerfile.portal`.
5. Resolve the Node build/runtime base to a digest before build.
6. Produce and retain SBOMs and vulnerability results.
7. Push images by immutable digest. Tags may exist for convenience but may not appear in the deployment manifest.
8. Record image digest ↔ source commit ↔ workflow run provenance.

## Secret preparation

OpenBao renders these six independent values before Compose runs:

```text
partner Keycloak client secret
partner portal session secret
operations Keycloak client secret
operations portal session secret
administration Keycloak client secret
administration portal session secret
```

Session secrets must have at least 32 characters of entropy. Files must be root-owned, non-symlinked, mode `0400`, `0440`, `0600`, or `0640`, and readable by the deployment process only. The environment file contains paths, never secret values.

## Staging certification

Run the deployment workflow with `environment=staging` and `apply=false`. Review the exact source, image digests, Compose validation, and ownership contract results. After issue #18 and all other blockers are closed, rerun with `apply=true` and obtain the `breero-staging` environment approval.

Certify each portal with a dedicated test account and no shared roles:

### Identity and session

- login uses Keycloak Authorization Code + PKCE
- state and nonce mismatch fail closed
- wrong portal role is rejected
- access token refresh occurs server-side
- logout destroys local session and reaches Keycloak logout
- session expiration and logout propagate across tabs
- browser storage contains no access or refresh token
- cookies are `__Host-`, Secure, HttpOnly, SameSite=Lax
- CSRF, cross-origin mutation, traversal, oversized body, timeout, and disallowed route tests fail closed

### Partner

- another vendor cannot be selected by request parameters
- profile, roster, service, skill, coverage, application, job, credential, earning, and payout-history reads are ownership scoped
- service version conflicts return a visible retry state
- credential verification, dispatch, compensation, and payout commands are inaccessible
- payout-disabled state remains truthful

### Operations

- dispatch queue is ordered and auditable
- contact, address, timezone, follow-up, and note changes create evidence
- matching is advisory and cannot auto-assign
- manual assignment requires provider, active/available technician, and reason
- conflicting or stale assignment fails safely
- provider state, credential, and application decisions require the correct permission and create audit records

### Administration and finance

- finance-only users cannot access users, geography, integrations, or audit controls
- role replacement requires explicit confirmation and backend authorization
- only superadmin can grant superadmin
- service zones are created inactive
- invalid GeoJSON, overlapping/invalid boundaries, bad timezone, and duplicate postal coverage fail cleanly
- compensation plans are effective-dated
- earning snapshots are immutable
- reviewer cannot approve the same payout batch
- approver cannot submit the same payout batch
- payout commands return disabled while the capability is false
- outbox activation remains blocked without every required private configuration signal

### Browser and accessibility

Test current stable Chrome, Edge, Firefox, and Safari, plus representative iOS and Android viewports. Require keyboard-only operation, visible focus, meaningful headings/labels, reduced-motion behavior, contrast compliance, responsive tables/forms, loading, empty, partial, error, timeout, offline, retry, and session-expired states.

### Observability

- `/metrics` is private and scraped
- HTTP route labels use templates, not raw identifiers
- API, PostgreSQL, Redis, Keycloak, Kong, and worker dependency state is visible
- outbox age/status and worker heartbeat alerts function
- a portal request correlation ID can be followed through Caddy, the BFF, Kong, API logs, trace storage, and durable outbox evidence
- logs redact Authorization, Cookie, query strings, request bodies, and secret paths

## Production release

1. Confirm staging certification evidence is attached to the change record.
2. Confirm backup/restore evidence and rollback rehearsal are current.
3. Close issues #17, #18, and #19 with evidence.
4. Apply the reviewed Keycloak client configuration from the Keycloak repository.
5. Apply the reviewed private API route from the Kong repository.
6. Apply the reviewed HTTPS hostname routes from the Caddy repository.
7. Verify OpenBao-rendered files and external Docker networks on the production host.
8. Run the portal deployment workflow with `environment=production`, the exact reviewed source commit, four digest images, the approved change ID, and `apply=false`.
9. Review the plan and obtain the `breero-production` environment approval.
10. Rerun the identical inputs with `apply=true`.
11. The workflow verifies fail-closed capabilities, pulls digests, applies Compose with `--wait`, tests all health endpoints and OIDC redirects, records evidence, and promotes the release symlink.
12. Perform role-by-role read-only canaries before authorizing any business mutation.

## Rollback

A failed apply automatically reapplies the previous release directory using its retained Compose file and environment manifest. For an operator-initiated rollback:

```bash
previous=/srv/breero-portals/releases/<previous-exact-sha>
docker compose \
  --env-file "$previous/portal.env" \
  -f "$previous/compose.yml" \
  up -d --wait --remove-orphans
ln -sfn "$previous" /srv/breero-portals/current
```

If identity or gateway changes caused the incident, roll those back only from their owning repositories. Do not bypass Kong, weaken Keycloak redirect rules, expose container ports, or enable a live capability to make a smoke test pass.

## Required release evidence

Retain:

- exact source commit and GitHub verification state
- exact required-check results and approvals
- four image digests and base-image digest
- SBOMs, vulnerability reports, provenance, and secret-scan result
- migration upgrade/rollback/drift evidence
- Keycloak, Kong, and Caddy exact-source apply evidence
- Compose validation and container hardening inventory
- staging role/browser/accessibility/security test evidence
- metrics/log/trace screenshots or query exports
- production health and OIDC smoke results
- previous release pointer and tested rollback result
- change ID, approver, operator, UTC timestamps, and final go/no-go decision
