# BREERO Marketplace V2 target-state frontend route registry

## Status and authority

This document defines the **target-state Marketplace V2 route namespace**. It is not an inventory of routes currently implemented on the accepted post-#34 runtime.

The current application remains whatever is present and verified on accepted `main`. Existing public, account, request, quote-only booking, policy, and compatibility routes must not be removed, redirected, shadowed, or replaced merely because a target route appears below.

Unless an independently reviewed implementation PR proves otherwise, every route in this document has status:

```text
TARGET_STATE_ONLY
NOT_IMPLEMENTED_BY_THIS_DOCUMENT
NOT_DEPLOYED
NOT_CAPABILITY_ACTIVATED
NOT_AUTHORIZATION_EVIDENCE
```

Route presence is navigation only. Backend identity, tenant membership, record policy, permission, and runtime capability checks remain authoritative.

## Implementation rules

- Add routes only in dependency-ordered implementation PRs based on the latest accepted `main`.
- Do not create placeholder success pages or fake portal data.
- Preserve existing routes until a reviewed compatibility and redirect plan is accepted.
- Fail closed when identity, authorization, tenant context, or a required capability is unavailable.
- Keep frontend visibility separate from backend authorization.
- Regenerate route, accessibility, responsive, and E2E evidence for every implemented route family.

Capability-sensitive examples:

```text
customer/provider messaging -> messaging capability
customer/provider reviews -> reviews capability
provider portal routes -> provider self-service capability plus tenant/RBAC
matching/opportunity routes -> marketplace matching capability plus record policy
admin/operations routes -> authenticated server-side permissions and tenant scope
```

## Public target routes

```text
/
/request
```

## Customer target routes

```text
/customer/dashboard
/customer/requests
/customer/matches
/customer/quotes
/customer/messages
/customer/bookings
/customer/jobs
/customer/reviews
/customer/disputes
/customer/properties
/customer/notifications
/customer/profile
```

## Provider target routes

```text
/provider/dashboard
/provider/onboarding
/provider/profile
/provider/services
/provider/service-area
/provider/workers
/provider/availability
/provider/credentials
/provider/opportunities
/provider/leads
/provider/quotes
/provider/messages
/provider/schedule
/provider/jobs
/provider/customers
/provider/reviews
/provider/disputes
/provider/analytics
```

## Worker target routes

```text
/worker/today
/worker/jobs
/worker/schedule
/worker/availability
/worker/credentials
```

## Operations target routes

```text
/ops/dashboard
/ops/requests
/ops/matching
/ops/opportunities
/ops/jobs
/ops/providers
/ops/exceptions
/ops/disputes
/ops/integrations
/ops/map
/ops/analytics
```

## Admin target routes

```text
/admin/dashboard
/admin/provider-applications
/admin/providers
/admin/credentials
/admin/users
/admin/roles
/admin/permissions
/admin/catalog
/admin/features
/admin/reviews
/admin/disputes
/admin/integrations
/admin/audit
/admin/system-status
/admin/releases
```

## Explicit non-authority

This registry does not authorize payments, payouts, paid leads, checkout, automatic booking, automatic assignment, automatic confirmation, provider self-service, matching, messaging, reviews, marketing, external sends, production deployment, or a change to the accepted quote-only/manual-scheduling release boundary.
