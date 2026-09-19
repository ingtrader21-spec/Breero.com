# BREERO frontend bootstrap safety

The frontend bootstrap and target-route documentation do not activate high-risk capabilities or authorize production behavior.

The accepted quote-only/manual-scheduling baseline may expose request intake and operator-confirmed scheduling routes. Route presence does not imply instant booking, automatic confirmation, settlement, provider self-service, or any other live capability.

## Required disabled boundaries

Until separately implemented, tested, independently approved, and explicitly activated through the authoritative backend capability registry:

```text
payments=false
payouts=false
paid_leads=false
instant_booking=false
automatic_booking=false
automatic_assignment=false
automatic_confirmation=false
provider_self_service=false
marketplace_matching=false
messaging=false
reviews=false
marketing=false
unrestricted_email=false
unrestricted_sms=false
external_automation=false
```

## Enforcement rules

- Frontend visibility is not authorization.
- Hidden navigation is not a security boundary.
- Backend identity, tenant membership, record policy, permissions, and capabilities remain authoritative.
- Missing or unreadable capability state must fail closed.
- A route, component, schema, mock, feature flag name, or documentation entry must never enable a capability by itself.
- No placeholder portal may claim data, actions, or completion that the authoritative backend cannot prove.
- Existing accepted routes must not be removed or redirected without a reviewed compatibility plan.
- No deployment, external send, payment, payout, paid-lead charge, provider assignment, or confirmation is part of frontend bootstrap work.

## Review evidence for future runtime changes

Every implementation PR must provide the relevant lint, typecheck, unit/component, accessibility, responsive, production-build, and E2E evidence, plus negative tests proving disabled or unavailable capabilities remain inaccessible and non-actionable.
