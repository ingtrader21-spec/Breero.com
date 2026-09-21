# Horizon portfolio-shell adoption

## Authority

- Horizon repository: `appolon1908-hue/SDK-repository`
- Foundation PR: `#73`
- Visual-contract exact head: `7db4c6549a0a007922355090f03c082a308f3855`
- Governance validator: `b258cf952df3a2ef11a2ba2e0df16c7983ee2a99`
- Adoption branch: `feature/horizon-portfolio-shell-v1`
- Product theme: `breero`
- Runtime activation: **not included**

`apps/web/app/horizon.css` is a generated adapter pinned to the visual contract. It is temporary until the shared `@codestra/intake-ui` package is released and can be consumed at an exact version. The operator suites use the shared token source in `packages/portal/src/styles.css`.

## Registered suites and canonical domains

| Suite | Surface | Canonical domain | Shell |
|---|---|---|---|
| `apps/web` | public marketplace and customer account | `https://breero.com` | shared public header/footer plus account frame |
| `apps/partner` | provider operator portal | `https://partners.breero.com` | shared Horizon operator rail/top bar |
| `apps/ops` | service operations | `https://ops.breero.com` | shared Horizon operator rail/top bar |
| `apps/admin` | administration and finance | `https://admin.breero.com` | shared Horizon operator rail/top bar |

Additional authorities:

| Role | Domain |
|---|---|
| Corporate authority | `https://codestra.co` |
| Identity host | `https://auth.codestra.co` |
| Canonical identity issuer | `https://auth.codestra.co/realms/codestra` |
| Shared API edge | `https://api.codestra.co` |

Public, partner, operations, administration, identity, and API domains are separate trust boundaries. A public header may link to another surface, but it must not treat an operator, identity, or API host as a public marketing route.

## Customer authentication

Breero has real account logic; the shared shell is connected to it rather than showing decorative authentication buttons.

- Keycloak mode uses Authorization Code Flow with PKCE S256.
- The compatibility customer API mode uses the canonical `/auth/login`, refresh, and `/auth/logout` operations.
- The public header reads the real customer session and displays either **Sign in** or **Account + Log out**.
- Protected `/account` pages fail closed through `AccountFrame` before account navigation or content renders.
- Logout attempts provider/API revocation, always clears Breero credentials locally, and never calls `sessionStorage.clear()`.
- Expired JWT access tokens are removed before a page is treated as authenticated.
- Post-login destinations are restricted to same-origin paths to prevent open redirects.
- Backend authorization remains authoritative for every protected read and command.
- The target durable identity is Keycloak `issuer + subject`; the current API-session compatibility path is migration-required.

Authoritative customer implementation files:

- `apps/web/components/account/auth-form.tsx`
- `apps/web/app/account/callback/page.tsx`
- `apps/web/lib/keycloak.ts`
- `apps/web/lib/customer/session-actions.ts`
- `apps/web/components/account/account-frame.tsx`
- `apps/web/components/account/account-nav.tsx`
- `apps/web/components/site-header.tsx`

## Operator authentication

Admin, operations, and partner applications all consume `@breero/portal`.

- Login calls the real `/auth/login` API.
- Restored sessions are rejected when expired or when their role is not allowed by the current portal.
- Every data request sends the bearer token to the configured secure API origin.
- HTTP 401 expires the local privileged session and returns the portal to login.
- Logout calls `/auth/logout` before fail-safe local cleanup.
- Admin, operations, finance, and provider roles are separate in the shell, while backend permission and record-level checks remain authoritative.
- No placeholder rows or invented operational values are shown when an API operation is unavailable.

Shared operator implementation:

- `packages/portal/src/index.tsx`
- `packages/portal/src/styles.css`
- `packages/portal/src/index.test.ts`

## Page and color rule

Every page inherits the registered root layout for its suite. New pages must inherit:

- `data-horizon-root`;
- `data-horizon-theme="breero"`;
- the public header/footer or approved operator-shell equivalent;
- the same typography, spacing, focus, form, card, table, and CTA hierarchy;
- applicable loading, empty, partial, stale, degraded, unauthorized, forbidden, validation-error, server-error, offline, and durable-success states.

New page and component files must not introduce raw product colors. Use Horizon variables such as `var(--hz-bg)`, `var(--hz-text)`, `var(--hz-accent)`, `var(--hz-border)`, `var(--hz-success)`, `var(--hz-warning)`, and `var(--hz-danger)`. Raw color definitions belong only in the registered token files.

## New suite rule

A new Breero application cannot be merged only by adding another `apps/*` directory. `horizon/suite.json` and `.github/workflows/horizon-contract.yml` enforce registration.

Before merge, a new suite must declare:

1. its canonical HTTPS domain and surface type;
2. its Horizon theme and root layout;
3. its header/footer or operator-shell equivalent;
4. its real login, session, route-guard, and logout implementation when protected routes exist;
5. its Keycloak client, issuer, scopes, audience, redirect/logout URIs, and allowed roles;
6. backend-authoritative permission, tenant, and record-level authorization;
7. its page-state, accessibility, build, test, security, deployment, and rollback evidence.

The validator rejects unregistered suites, fake login/logout controls, missing root-shell markers, missing auth source files, noncanonical OIDC issuers, and newly added raw colors outside registered token files.

## Preserved behavior

- booking CTA and analytics attributes;
- customer account and booking routes;
- marketing navigation and mobile Escape-key handling;
- service, legal, privacy, consent, and professional links;
- legal identity and no-online-payment disclosure;
- role-scoped operator navigation and live-API-only data;
- Next.js metadata and current brand assets.

## Validation

```bash
pnpm install --frozen-lockfile
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm --filter @breero/web test:e2e
```

This branch changes source only. It does not activate providers, payments, DNS, production identity configuration, deployment, secrets, or live runtime traffic.
