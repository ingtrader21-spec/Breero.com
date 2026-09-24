# Breero Horizon design-authority convergence

## PAS-111 authority

PAS-111 converges the two previously separate frontend authorities:

- enterprise design governance: PR #67, source branch `fe/enterprise-design-governance`;
- Horizon portfolio shell: PR #117, source branch `feature/horizon-portfolio-shell-v1`.

The result is one Breero design authority. Horizon is a shell contract inside the Breero design system, not a second visual system.

## Source pins

- Breero design-governance source head: `383ef98be7bf62bdd5f7e17552dd81e8480c0bc5`
- Horizon source head: `48666215246b748b0f276d25fd4f07e6654c691f`
- shared protected-main base: `5992759bfb8bc63fe030cefbfcac0a3024c35c78`
- Horizon foundation source: `appolon1908-hue/SDK-repository#73`
- Horizon foundation exact head: `7db4c6549a0a007922355090f03c082a308f3855`

## Single style authority

The public web app imports exactly one Breero enterprise design stylesheet:

`apps/web/app/enterprise-design-system.css`

The Horizon shell and compatibility rules are folded into that file under the marker:

`PAS-111 HORIZON SHELL CONVERGENCE`

The root layout must not import `horizon.css` or `horizon-compatibility.css`. This prevents parallel token systems and makes the Breero enterprise design system the single visual authority.

Shared marketplace primitives continue to come from:

- `@breero/ui/styles.css`
- `@breero/ui/marketplace.css`

## Public shell contract

The public Breero shell preserves the Horizon structural contract while keeping the accepted request-first product truth:

- `data-horizon-root`
- `data-horizon-theme="breero"`
- canonical Breero domain labeling
- responsive desktop/mobile navigation
- real customer session readback and logout
- partner-portal boundary link
- shared legal/support/domain footer structure
- Codestra product-network links

Global conversion language is **Request service**. The shared header and footer must not promise an immediate booking while provider eligibility, capacity, price, and assignment remain subject to authoritative backend confirmation.

## Registered product surfaces

| Surface | Canonical domain | Role |
|---|---|---|
| Public marketplace/customer | `https://breero.com` | request, discovery, customer account |
| Partner | `https://partners.breero.com` | provider operator portal |
| Operations | `https://ops.breero.com` | service operations |
| Administration | `https://admin.breero.com` | administration and finance |

The registered suite contract is stored in `horizon/suite.json`.

## Authentication and authorization

The shell may display authentication state, but backend authorization remains authoritative.

- customer session state uses the existing Keycloak/API compatibility paths;
- protected account views fail closed;
- logout clears local credentials even if upstream revocation fails;
- operator portals remain role-scoped;
- no shell element grants permissions by itself.

## Accessibility and responsive contract

The converged shell must preserve:

- keyboard-accessible navigation and Escape dismissal;
- focus visibility;
- reduced-motion behavior;
- semantic landmark/navigation structure;
- 320px through 1440px+ responsive layouts;
- truthful loading, empty, error, restricted, disabled, and success states;
- no fabricated providers, ratings, availability, pricing, guarantees, or completion state.

## Governance

`scripts/check-design-system.mjs` is the binding repository guard for this convergence. It requires the Horizon root markers, the folded Horizon rules inside the single enterprise stylesheet, the request-first header/footer contract, marketplace primitives, and aggregate design quality enforcement.

Changes to this document, `horizon/suite.json`, the enterprise stylesheet, shared shell components, or the design guard require CODEOWNER review.

## Validation

Required PAS-111 acceptance:

```bash
pnpm install --frozen-lockfile
pnpm test:design
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm --filter @breero/web test:e2e
```

Completion additionally requires exact-head hosted CI, independent review, governed merge, and post-merge verification. This convergence changes source only and does not activate payments, provider dispatch, DNS, secrets, or production traffic.
