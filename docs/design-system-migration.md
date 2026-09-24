# BREERO Design System Migration

## Current state

BREERO already has centralized brand assets, Manrope, shared UI primitives, a global AppShell, SiteHeader, SiteFooter, responsive public pages, protected workspaces, and an approved visual-system document. The enterprise and marketplace layers strengthen those foundations rather than replacing them.

The repository remains a supported FastAPI/Next.js modular monolith. This migration does not authorize a rewrite to another backend, frontend, cloud, database, identity, or deployment stack.

## Migration rule

Do not perform a risky one-shot rewrite of every existing page. Existing accepted CSS may remain until the page is touched for product work. New or materially edited UI must follow:

```text
docs/design-system.md
docs/marketplace-experience-system.md
```

## Sequence

1. Keep the global shell and enterprise layer stable.
2. Load the shared `@breero/ui/marketplace.css` authority in the public application.
3. Route all new CTA work through shared button variants.
4. Use `MarketplaceServiceCard` for service discovery.
5. Use `ProviderTrustCard` and distinct trust facts for provider evidence.
6. Use `CapacitySignal` only for authoritative capacity or dispatcher-review state.
7. Use `ProjectStatusTimeline` for request, quote, booking, assignment, job, support, compliance and dispute progress.
8. Implement explicit loading, empty, error, restricted, disabled and success states with `MarketplaceStatePanel` or an equivalent shared pattern.
9. Move new colors into central tokens instead of page CSS.
10. Remove page-local typography declarations when a page is materially edited.
11. Replace decorative pill buttons with the corporate radius system except where pill geometry communicates status or tags.
12. Consolidate repeated layout patterns into `@breero/ui` or shared application components.
13. Preserve verified accessibility and responsive behavior during each migration.
14. Keep product/application routes truthful to runtime capabilities; visual polish must never imply an unavailable booking, payment, provider, messaging, review, matching or assignment capability.

## Route-family order

Migrate route families in dependency order rather than visual convenience:

```text
public service discovery and request intake
customer request/quote/booking history
provider onboarding, profile and compliance
provider services, coverage, schedule and capacity
worker assigned-job experience
operations request queue and manual dispatch
trust/compliance review
support cases and communication history
admin catalog, zones, hours, flags, audit and system health
messaging, reviews, payments and sponsored placement only after their domain gates
```

## Acceptance for a migrated page

A page is complete when:

- it inherits the correct global or protected shared shell;
- no new raw visual values bypass central tokens;
- CTA hierarchy is unambiguous and capability truthful;
- request, quote, booking, assignment and completion states are distinct;
- service pricing mode is explicit when relevant;
- provider trust is evidence-specific;
- capacity and availability are not inferred in the browser;
- loading, empty, error, restricted, disabled and success states are deliberate;
- search/filter/sort/pagination is server-safe;
- forms preserve recoverable input and surface backend validation/correlation evidence;
- drawers/dialogs have accessible focus and stale-record handling;
- focus and keyboard behavior works;
- 320px and 375px mobile have no horizontal overflow;
- reduced-motion behavior is respected;
- no fabricated proof, metrics, ratings, availability, capacity, providers, prices or guarantees appear;
- applicable API, authorization, tenant, ownership, capability and persistence behavior is tested;
- `pnpm test:design`, lint, typecheck, tests, API-contract checks and production build pass for the exact head;
- Chromium, Firefox and WebKit pass for critical changed journeys;
- fresh review applies to the unchanged final SHA.

## Non-authority

This migration does not:

```text
activate instant booking
activate automatic provider assignment
activate automatic confirmation
activate payments or payouts
activate messaging, reviews or marketing
write production data
deploy containers
change DNS, Caddy or Kong
install a replacement architecture
```
