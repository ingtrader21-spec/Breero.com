## Scope

Describe the user-visible or architectural change and the branch responsibility.

## Design-system compliance

- [ ] I used BREERO brand tokens and shared UI primitives.
- [ ] I used the shared marketplace patterns for service, provider trust, capacity, lifecycle and data states where applicable.
- [ ] I did not add page-local colors, fonts, inline visual styles, or a parallel CSS system.
- [ ] CTA hierarchy is primary / outline / ghost / danger and uses shared button primitives.
- [ ] New public UI inherits the global SiteHeader and SiteFooter.
- [ ] Mobile, keyboard focus, screen-reader semantics, reduced motion and reflow were considered.
- [ ] I implemented explicit loading, empty, error, restricted, disabled and success behavior for changed data surfaces.
- [ ] I did not invent ratings, reviews, pricing, availability, capacity, guarantees, certifications, providers, bookings or capability claims.
- [ ] Request, quote, booking, assignment and completion language matches authoritative backend state.
- [ ] Search/filter/sort/pagination behavior remains server-safe and does not load an entire production table into the browser.
- [ ] Forms preserve recoverable input, prevent duplicate submission and show backend validation/correlation evidence.
- [ ] `pnpm test:design` passes on the complete comparison range.

## API and authorization

- [ ] Every changed interaction maps to a documented API operation or is explicitly marked overview-only.
- [ ] Authentication, permission, tenant, ownership, resource state and capability behavior were tested where applicable.
- [ ] No UI-only flag or hidden button is treated as an authorization boundary.

## Validation

Record exact-head frozen install, dependency audit, lint, typecheck, tests, API contract, production build, browser, accessibility, responsive and design-guard evidence relevant to this change.

## Deployment

- [ ] This PR does not deploy or mutate the live server unless explicitly documented and approved in a dedicated release/deployment PR.
- [ ] Protected production capabilities remain disabled unless a separate activation change is included and authorized.
