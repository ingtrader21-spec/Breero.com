# BREERO Enterprise Design System

Status: **binding frontend governance**

This layer keeps BREERO's approved identity and applies disciplined Fortune 500 visual behavior: restrained motion, high contrast, deliberate spacing, precise geometry, strong typography, one CTA hierarchy, and truthful product state. It does **not** copy Angi, SpaceX, Starlink, or any third-party logo, asset, font, page composition, proprietary artwork, or marketing claim.

The companion `docs/marketplace-experience-system.md` is the binding interaction and marketplace-state authority.

## Brand authority

The existing BREERO visual authority remains canonical:

- Primary blue: `#146EF5`
- Primary blue dark: `#0E52C6`
- Deep navy: `#0B1F3A`
- Ink: `#10243E`
- Teal: `#18B7A0`
- Coral: `#FF6B6B`
- Sun yellow: `#FFC857`
- White and approved neutral surfaces from `docs/brand/BREERO_VISUAL_SYSTEM.md`

The enterprise layer uses navy/white as the high-trust shell and BREERO blue for primary actions. Accent colors remain secondary. Codestra yellow is **not** BREERO's primary CTA color.

## Typography

BREERO uses **Manrope first** through Next.js font optimization. It is the single display/body family for the enterprise shell.

Fallback stack:

`Manrope, "Helvetica Neue", "Segoe UI", Arial, sans-serif`

Rules:

- navigation and compact CTA labels may use uppercase with controlled tracking;
- headings use tight tracking and balanced wrapping;
- body copy remains sentence case;
- marketing copy is never below 14px;
- page code must not introduce another font family or external font request.

## CTA hierarchy

Use shared `.br-button` primitives only.

1. **Primary** — BREERO blue; one dominant action per decision surface.
2. **Outline** — transparent/neutral supporting action.
3. **Ghost** — low-priority navigation or utility.
4. **Danger** — destructive actions only.

Required interaction rules:

- minimum practical target: 44px;
- default enterprise button: 50px;
- compact CTA: 44px minimum;
- large CTA: 54px;
- small corporate radius, never decorative pills for ordinary CTAs;
- keyboard-visible focus and reduced-motion support;
- CTA language must match authoritative request, quote, booking, assignment, payment, review, messaging and capability state.

The accepted global shell is request-first. The primary global action is **Request service**, not an unsupported instant-booking promise.

## Header

The global header is the application shell authority:

- 76px desktop / 70px mobile;
- dark navy high-trust shell;
- BREERO logo left;
- centered desktop navigation where space allows;
- account + truthful primary CTA right;
- accessible mobile navigation;
- no page-local replacement headers.

## Footer

The global footer contains:

- final request-service conversion section;
- BREERO positioning and legal identity;
- services, company, support, privacy/communications, and professional navigation;
- legal/privacy/accessibility links;
- no fake metrics, reviews, service availability, provider assignment, pricing, or guarantees.

## Layout and spacing

Use the existing container and an 8px-derived spacing rhythm.

- major sections: approximately 72–120px desktop and 48–72px mobile;
- one primary content axis per section;
- prefer asymmetry and whitespace over dense card walls;
- cards use the shared radius/border system;
- avoid heavy black shadows and excessive gradients;
- animation must be functional, restrained, and removable through reduced-motion.

## Marketplace primitives

`@breero/ui` owns the shared marketplace patterns:

```text
MarketplaceServiceCard
PricingModeBadge
ProviderTrustCard
TrustBadge
CapacitySignal
ProjectStatusTimeline
MarketplaceStatePanel
```

Use them for new or materially edited service, provider, customer, worker, dispatch, support, trust, quality, finance and administration experiences.

The components display authoritative facts; they do not perform scheduling, eligibility, matching, assignment, payment, verification, or state transitions.

### Pricing modes

```text
INSTANT_BOOKABLE
QUOTE_REQUIRED
REQUEST_ONLY
```

Do not infer a pricing mode from frontend copy or route shape.

### Trust facts

```text
IDENTITY
BUSINESS
LICENSE
INSURANCE
BACKGROUND SCREENING
SERVICE QUALIFICATION
```

Trust facts use distinct verified, pending, expired, or not-required states. Do not replace them with a vague universal verified badge.

### Capacity states

```text
AVAILABLE
LIMITED
DISPATCHER REVIEW
UNAVAILABLE
```

Capacity display must come from the authoritative scheduling/capacity service or an explicit dispatcher-review state.

### Complete data states

Every changed data surface deliberately handles:

```text
LOADING
EMPTY
ERROR
RESTRICTED
DISABLED
SUCCESS
```

Blank pages, fake cards, perpetual spinners, and silent failures are not acceptable.

## Page inheritance

`RootLayout -> AppShell -> SiteHeader + main + SiteFooter` is the required shell. New public pages automatically inherit the same header, footer, typography, focus rules, CTA primitives, marketplace stylesheet, and enterprise layer. Page-local parallel shells are prohibited.

Department and account applications may use protected workspace shells, but they must reuse the same tokens, UI package, state vocabulary, trust evidence, lifecycle status and accessibility rules.

## Search, forms, drawers and lists

- production lists use server-side search, filter, sort and pagination;
- forms preserve recoverable input and use backend validation/correlation evidence;
- unchanged retries retain the same idempotency identity where required;
- drawers and dialogs have focus management, accessible titles and safe stale-record behavior;
- buttons must have real actions, documented routes, or an explicit disabled/overview-only explanation;
- protected capability absence is never hidden behind a fake success state.

## Responsive and accessibility baseline

Validate at 320, 375, 390, 430, 768, 1024 and 1440+ CSS pixels.

Required checks include:

- keyboard operation and visible focus;
- screen-reader labels, status announcements and heading order;
- accessible forms, errors, dialogs, drawers and timelines;
- status not communicated by color alone;
- reduced motion;
- reflow and 200% zoom;
- Chromium, Firefox and WebKit.

## Design drift guard

Run:

```bash
pnpm test:design
```

The guard checks changed code and fails on newly introduced design drift including:

- literal HEX/RGB/HSL colors outside approved token/style authorities;
- inline visual styles;
- page/component font-family declarations;
- new CSS systems outside approved central style files;
- arbitrary Tailwind-style values and palette utilities;
- decorative full-pill geometry in ordinary page/component changes;
- root layout losing the shared marketplace or enterprise layer;
- AppShell losing the shared header/footer;
- header losing the shared BREERO logo or truthful request CTA;
- shared marketplace primitives, stylesheet, tests or authority disappearing;
- required governance files disappearing.

The guard intentionally evaluates **added lines in the complete comparison range**, not just the final commit, so a violation cannot be hidden by a later unrelated commit.

## Exceptions

A genuine design-system change must be made in the approved central style authorities and reviewed as a design-system change. Do not bypass the guard in a page file. If a new token or marketplace pattern is required, add it centrally, document it, test it, and use it everywhere else.
