# Current BREERO system

Generated from executable source inventory at `50407f46777e44fb0efbd6af0c7b70466a43a93d`. This is source truth only; deployed database revision, external services, and production activation require separate runtime certification.

## Canonical source record

| Field | Source evidence |
|---|---|
| REPOSITORY | `ingtrader21-spec/Breero.com` |
| SOURCE_SHA | `50407f46777e44fb0efbd6af0c7b70466a43a93d` |
| ALEMBIC_HEADS | `031_provider_catalog` |
| ALEMBIC_REVISIONS | 32 |
| OPENAPI_ARTIFACT | `apps/api/openapi.json` / `7c2ea4ffaa0b79705f8c0298eca24526268c8db86906491a5214384a0e7f05bf` |
| BACKEND_DOMAINS | 17 |
| FRONTEND_ROUTES | 91 |
| WORKER_TASKS | 4 |
| DEPLOYMENT_FILES | 11 |
| LIVE_PRODUCTION_CERTIFICATION | NOT ESTABLISHED BY THIS INVENTORY |

Stale PR/issue counts are intentionally not copied into this source document. GitHub state must be verified live when a release or mission decision depends on it.

## Runtime/API profiles

| Profile | OpenAPI paths | OpenAPI operations | Checked artifact match | Duplicate registrations |
|---|---:|---:|---|---:|
| canonical_contract | 154 | 188 | TRUE | 8 |
| default | 145 | 178 | FALSE | 5 |
| implemented_routes | 167 | 200 | FALSE | 5 |

The `canonical_contract` profile is the checked-in OpenAPI authority. The default profile is the fail-closed route surface; implemented/dark profiles are evidence of code presence, not authorization to activate capabilities.

## Route ambiguity evidence

Profile-contract variants: **3**. Duplicate registrations remain explicit evidence for the API-authority mission; they are not silently collapsed into a claim of unique ownership.

### canonical_contract

| Method | Path | Registrations |
|---|---|---|
| GET | `/api/v1/admin/provider-applications` | apps/api/app/api/v1/provider_onboarding.py::list_provider_applications; apps/api/app/api/v1/admin.py::provider_applications |
| GET | `/api/v1/provider/profile` | apps/api/app/api/v1/provider_onboarding.py::provider_profile; apps/api/app/api/v1/provider.py::profile |
| GET | `/api/v1/provider/services` | apps/api/app/api/v1/provider_catalog.py::list_provider_services; apps/api/app/api/v1/provider.py::services |
| POST | `/api/v1/admin/users` | apps/api/app/api/v1/admin_users.py::provision_internal_user; apps/api/app/api/v1/admin.py::create_admin_user |
| POST | `/api/v1/booking/address/validate` | apps/api/app/api/v1/booking_geography.py::validate_booking_address; apps/api/app/api/v1/public_booking.py::validate_address |
| POST | `/api/v1/booking/service-area/check` | apps/api/app/api/v1/booking_geography.py::check_booking_service_area; apps/api/app/api/v1/public_booking.py::check_service_area |
| POST | `/api/v1/booking/timezone/resolve` | apps/api/app/api/v1/booking_geography.py::resolve_booking_timezone; apps/api/app/api/v1/public_booking.py::resolve_timezone |
| POST | `/api/v1/provider/services` | apps/api/app/api/v1/provider_catalog.py::add_provider_service; apps/api/app/api/v1/provider.py::add_service |

### default

| Method | Path | Registrations |
|---|---|---|
| GET | `/api/v1/admin/provider-applications` | apps/api/app/api/v1/provider_onboarding.py::list_provider_applications; apps/api/app/api/v1/admin.py::provider_applications |
| GET | `/api/v1/provider/profile` | apps/api/app/api/v1/provider_onboarding.py::provider_profile; apps/api/app/api/v1/provider.py::profile |
| GET | `/api/v1/provider/services` | apps/api/app/api/v1/provider_catalog.py::list_provider_services; apps/api/app/api/v1/provider.py::services |
| POST | `/api/v1/admin/users` | apps/api/app/api/v1/admin_users.py::provision_internal_user; apps/api/app/api/v1/admin.py::create_admin_user |
| POST | `/api/v1/provider/services` | apps/api/app/api/v1/provider_catalog.py::add_provider_service; apps/api/app/api/v1/provider.py::add_service |

### implemented_routes

| Method | Path | Registrations |
|---|---|---|
| GET | `/api/v1/admin/provider-applications` | apps/api/app/api/v1/provider_onboarding.py::list_provider_applications; apps/api/app/api/v1/admin.py::provider_applications |
| GET | `/api/v1/provider/profile` | apps/api/app/api/v1/provider_onboarding.py::provider_profile; apps/api/app/api/v1/provider.py::profile |
| GET | `/api/v1/provider/services` | apps/api/app/api/v1/provider_catalog.py::list_provider_services; apps/api/app/api/v1/provider.py::services |
| POST | `/api/v1/admin/users` | apps/api/app/api/v1/admin_users.py::provision_internal_user; apps/api/app/api/v1/admin.py::create_admin_user |
| POST | `/api/v1/provider/services` | apps/api/app/api/v1/provider_catalog.py::add_provider_service; apps/api/app/api/v1/provider.py::add_service |

## Backend domains

| Directory under apps/api/app/domains | Source state |
|---|---|
| `administration` | SOURCE_PRESENT |
| `auth` | SOURCE_PRESENT |
| `booking` | SOURCE_PRESENT |
| `booking_intents` | SOURCE_PRESENT |
| `capabilities` | SOURCE_PRESENT |
| `catalog` | SOURCE_PRESENT |
| `common` | SOURCE_PRESENT |
| `compliance` | SOURCE_PRESENT |
| `dispatch` | SOURCE_PRESENT |
| `finance` | SOURCE_PRESENT |
| `geography` | SOURCE_PRESENT |
| `jobs` | SOURCE_PRESENT |
| `payments` | SOURCE_PRESENT |
| `professional_leads` | SOURCE_PRESENT |
| `provider_catalog` | SOURCE_PRESENT |
| `public_submissions` | SOURCE_PRESENT |
| `workforce` | SOURCE_PRESENT |

Functional completeness is intentionally not inferred from directory presence. Domain acceptance remains governed by the M00–M30 mission board.

## Worker tasks

| Source | Function | Configuration |
|---|---|---|
| [apps/api/app/workers/tasks.py](../../apps/api/app/workers/tasks.py) | `expire_bookings` | `{"name": "app.workers.tasks.expire_bookings"}` |
| [apps/api/app/workers/tasks.py](../../apps/api/app/workers/tasks.py) | `publish_outbox` | `{"autoretry_for": "DYNAMIC", "max_retries": 5, "name": "app.workers.tasks.publish_outbox", "retry_backoff": true}` |
| [apps/api/app/workers/tasks.py](../../apps/api/app/workers/tasks.py) | `release_earnings` | `{"name": "app.workers.tasks.release_earnings"}` |
| [apps/api/app/workers/tasks.py](../../apps/api/app/workers/tasks.py) | `generate_weekly_payout_candidates` | `{"name": "app.workers.tasks.generate_weekly_payout_candidates"}` |

## Deployment definitions

| Path | SHA-256 |
|---|---|
| [deploy/frontend/docker-compose.frontend.yml](../../deploy/frontend/docker-compose.frontend.yml) | `3e11d5d8a3a7b39a8250d4fc690326243e64fe7e33602603d946324137ab1f6d` |
| [deploy/observability/docker-compose.observability.yml](../../deploy/observability/docker-compose.observability.yml) | `4548a59202bb998c16cec41df30a230c88398dd7ebe166cfd974579fb04c73db` |
| [deploy/observability/otel-collector-breero.yaml](../../deploy/observability/otel-collector-breero.yaml) | `7636e550bdfa654b31c256970c957909fc51efb0113c5cd78cc7b7cd11527b7c` |
| [deploy/observability/prometheus-breero.yml](../../deploy/observability/prometheus-breero.yml) | `ed251579d8b2886f24a0fee47c982a6ad9be83ccc7d18fbf4e3b2bb2e939858b` |
| [deploy/portals/docker-compose.portals.yml](../../deploy/portals/docker-compose.portals.yml) | `d5d9b86a4d3144869ccf07a952541bd8b2fad3e0ffd972e8e321e109e5416af6` |
| [deploy/production/docker-compose.backend.yml](../../deploy/production/docker-compose.backend.yml) | `6cfceb34ef0772c856b9bea8da9fb7bc63e664e89693db668bf3b5420b9d99ac` |
| [deploy/staging/docker-compose.backend.yml](../../deploy/staging/docker-compose.backend.yml) | `150da1d0fd965bcea84a5bd8ce894b478f811a0d092c7100e075e78bc5bf52fd` |
| [deploy/staging/docker-compose.middleware.yml](../../deploy/staging/docker-compose.middleware.yml) | `33f2371b8f76171b22e293dd110b919b04044eb272968356c5bfaee12644cf60` |
| [docker-compose.middleware.yml](../../docker-compose.middleware.yml) | `4fbb1ff7e95f0be2efff51fe0787424a43a1e9c6701e99a66c293297aa69aefb` |
| [docker-compose.production.yml](../../docker-compose.production.yml) | `be0cbbfc4e5217e007d358a15f67d7ba4e38d44783c139b98a3a0eb763c6378d` |
| [docker-compose.yml](../../docker-compose.yml) | `b04c45a9227e012944df693326daaf498e5754aa81402cecdc8578b04e2a34e8` |

## All frontend routes

Filesystem route presence is source evidence, not proof of authentication, accessibility, real-data completeness, or deployed reachability.

| App | Kind | Route | Source |
|---|---|---|---|
| web | page | `/forgot-password` | [apps/web/app/(auth)/forgot-password/page.tsx](../../apps/web/app/(auth)/forgot-password/page.tsx) |
| web | page | `/login` | [apps/web/app/(auth)/login/page.tsx](../../apps/web/app/(auth)/login/page.tsx) |
| web | page | `/register` | [apps/web/app/(auth)/register/page.tsx](../../apps/web/app/(auth)/register/page.tsx) |
| web | page | `/reset-password` | [apps/web/app/(auth)/reset-password/page.tsx](../../apps/web/app/(auth)/reset-password/page.tsx) |
| web | page | `/verify-email` | [apps/web/app/(auth)/verify-email/page.tsx](../../apps/web/app/(auth)/verify-email/page.tsx) |
| web | page | `/about` | [apps/web/app/about/page.tsx](../../apps/web/app/about/page.tsx) |
| web | page | `/access-denied` | [apps/web/app/access-denied/page.tsx](../../apps/web/app/access-denied/page.tsx) |
| web | page | `/accessibility` | [apps/web/app/accessibility/page.tsx](../../apps/web/app/accessibility/page.tsx) |
| web | page | `/account/addresses` | [apps/web/app/account/addresses/page.tsx](../../apps/web/app/account/addresses/page.tsx) |
| web | page | `/account/bookings/[id]` | [apps/web/app/account/bookings/[id]/page.tsx](../../apps/web/app/account/bookings/[id]/page.tsx) |
| web | page | `/account/bookings` | [apps/web/app/account/bookings/page.tsx](../../apps/web/app/account/bookings/page.tsx) |
| web | page | `/account/callback` | [apps/web/app/account/callback/page.tsx](../../apps/web/app/account/callback/page.tsx) |
| web | page | `/account/forbidden` | [apps/web/app/account/forbidden/page.tsx](../../apps/web/app/account/forbidden/page.tsx) |
| web | page | `/account/forgot-password` | [apps/web/app/account/forgot-password/page.tsx](../../apps/web/app/account/forgot-password/page.tsx) |
| web | page | `/account/login` | [apps/web/app/account/login/page.tsx](../../apps/web/app/account/login/page.tsx) |
| web | page | `/account` | [apps/web/app/account/page.tsx](../../apps/web/app/account/page.tsx) |
| web | page | `/account/payments/[id]` | [apps/web/app/account/payments/[id]/page.tsx](../../apps/web/app/account/payments/[id]/page.tsx) |
| web | page | `/account/payments` | [apps/web/app/account/payments/page.tsx](../../apps/web/app/account/payments/page.tsx) |
| web | page | `/account/profile` | [apps/web/app/account/profile/page.tsx](../../apps/web/app/account/profile/page.tsx) |
| web | page | `/account/quotes/[id]` | [apps/web/app/account/quotes/[id]/page.tsx](../../apps/web/app/account/quotes/[id]/page.tsx) |
| web | page | `/account/quotes` | [apps/web/app/account/quotes/page.tsx](../../apps/web/app/account/quotes/page.tsx) |
| web | page | `/account/register` | [apps/web/app/account/register/page.tsx](../../apps/web/app/account/register/page.tsx) |
| web | page | `/account/reset-password` | [apps/web/app/account/reset-password/page.tsx](../../apps/web/app/account/reset-password/page.tsx) |
| web | page | `/account/session-expired` | [apps/web/app/account/session-expired/page.tsx](../../apps/web/app/account/session-expired/page.tsx) |
| web | page | `/account/unauthorized` | [apps/web/app/account/unauthorized/page.tsx](../../apps/web/app/account/unauthorized/page.tsx) |
| web | page | `/account/verify` | [apps/web/app/account/verify/page.tsx](../../apps/web/app/account/verify/page.tsx) |
| web | page | `/admin` | [apps/web/app/admin/page.tsx](../../apps/web/app/admin/page.tsx) |
| web | handler | `/api/addresses/validate` | [apps/web/app/api/addresses/validate/route.ts](../../apps/web/app/api/addresses/validate/route.ts) |
| web | handler | `/api/capabilities` | [apps/web/app/api/capabilities/route.ts](../../apps/web/app/api/capabilities/route.ts) |
| web | handler | `/api/communications/preferences` | [apps/web/app/api/communications/preferences/route.ts](../../apps/web/app/api/communications/preferences/route.ts) |
| web | handler | `/api/privacy-requests` | [apps/web/app/api/privacy-requests/route.ts](../../apps/web/app/api/privacy-requests/route.ts) |
| web | handler | `/api/public-submissions/[kind]` | [apps/web/app/api/public-submissions/[kind]/route.ts](../../apps/web/app/api/public-submissions/[kind]/route.ts) |
| web | handler | `/api/services` | [apps/web/app/api/services/route.ts](../../apps/web/app/api/services/route.ts) |
| web | page | `/availability` | [apps/web/app/availability/page.tsx](../../apps/web/app/availability/page.tsx) |
| web | page | `/become-a-provider` | [apps/web/app/become-a-provider/page.tsx](../../apps/web/app/become-a-provider/page.tsx) |
| web | page | `/blog` | [apps/web/app/blog/page.tsx](../../apps/web/app/blog/page.tsx) |
| web | page | `/book` | [apps/web/app/book/page.tsx](../../apps/web/app/book/page.tsx) |
| web | page | `/booking` | [apps/web/app/booking/page.tsx](../../apps/web/app/booking/page.tsx) |
| web | page | `/brand-preview` | [apps/web/app/brand-preview/page.tsx](../../apps/web/app/brand-preview/page.tsx) |
| web | page | `/cancellation-policy` | [apps/web/app/cancellation-policy/page.tsx](../../apps/web/app/cancellation-policy/page.tsx) |
| web | page | `/careers` | [apps/web/app/careers/page.tsx](../../apps/web/app/careers/page.tsx) |
| web | page | `/communications-preferences` | [apps/web/app/communications-preferences/page.tsx](../../apps/web/app/communications-preferences/page.tsx) |
| web | page | `/contact` | [apps/web/app/contact/page.tsx](../../apps/web/app/contact/page.tsx) |
| web | page | `/cookie-preferences` | [apps/web/app/cookie-preferences/page.tsx](../../apps/web/app/cookie-preferences/page.tsx) |
| web | page | `/cookies` | [apps/web/app/cookies/page.tsx](../../apps/web/app/cookies/page.tsx) |
| web | page | `/emergency` | [apps/web/app/emergency/page.tsx](../../apps/web/app/emergency/page.tsx) |
| web | page | `/faq` | [apps/web/app/faq/page.tsx](../../apps/web/app/faq/page.tsx) |
| web | page | `/finance` | [apps/web/app/finance/page.tsx](../../apps/web/app/finance/page.tsx) |
| web | handler | `/health` | [apps/web/app/health/route.ts](../../apps/web/app/health/route.ts) |
| web | page | `/help` | [apps/web/app/help/page.tsx](../../apps/web/app/help/page.tsx) |
| web | page | `/home-care` | [apps/web/app/home-care/page.tsx](../../apps/web/app/home-care/page.tsx) |
| web | page | `/how-it-works` | [apps/web/app/how-it-works/page.tsx](../../apps/web/app/how-it-works/page.tsx) |
| web | page | `/landing/[slug]` | [apps/web/app/landing/[slug]/page.tsx](../../apps/web/app/landing/[slug]/page.tsx) |
| web | page | `/lead-terms` | [apps/web/app/lead-terms/page.tsx](../../apps/web/app/lead-terms/page.tsx) |
| web | page | `/locations/[slug]` | [apps/web/app/locations/[slug]/page.tsx](../../apps/web/app/locations/[slug]/page.tsx) |
| web | page | `/locations` | [apps/web/app/locations/page.tsx](../../apps/web/app/locations/page.tsx) |
| web | page | `/marketing` | [apps/web/app/marketing/page.tsx](../../apps/web/app/marketing/page.tsx) |
| web | page | `/ops` | [apps/web/app/ops/page.tsx](../../apps/web/app/ops/page.tsx) |
| web | page | `/` | [apps/web/app/page.tsx](../../apps/web/app/page.tsx) |
| web | page | `/partners` | [apps/web/app/partners/page.tsx](../../apps/web/app/partners/page.tsx) |
| web | page | `/press` | [apps/web/app/press/page.tsx](../../apps/web/app/press/page.tsx) |
| web | page | `/pricing` | [apps/web/app/pricing/page.tsx](../../apps/web/app/pricing/page.tsx) |
| web | page | `/privacy` | [apps/web/app/privacy/page.tsx](../../apps/web/app/privacy/page.tsx) |
| web | page | `/privacy-choices` | [apps/web/app/privacy-choices/page.tsx](../../apps/web/app/privacy-choices/page.tsx) |
| web | page | `/professional-lead-policy` | [apps/web/app/professional-lead-policy/page.tsx](../../apps/web/app/professional-lead-policy/page.tsx) |
| web | page | `/provider` | [apps/web/app/provider/page.tsx](../../apps/web/app/provider/page.tsx) |
| web | page | `/provider-terms` | [apps/web/app/provider-terms/page.tsx](../../apps/web/app/provider-terms/page.tsx) |
| web | page | `/quality` | [apps/web/app/quality/page.tsx](../../apps/web/app/quality/page.tsx) |
| web | page | `/refund-cancellation` | [apps/web/app/refund-cancellation/page.tsx](../../apps/web/app/refund-cancellation/page.tsx) |
| web | page | `/refund-policy` | [apps/web/app/refund-policy/page.tsx](../../apps/web/app/refund-policy/page.tsx) |
| web | page | `/request-service` | [apps/web/app/request-service/page.tsx](../../apps/web/app/request-service/page.tsx) |
| web | page | `/reviews` | [apps/web/app/reviews/page.tsx](../../apps/web/app/reviews/page.tsx) |
| web | page | `/sales` | [apps/web/app/sales/page.tsx](../../apps/web/app/sales/page.tsx) |
| web | page | `/service-fulfillment` | [apps/web/app/service-fulfillment/page.tsx](../../apps/web/app/service-fulfillment/page.tsx) |
| web | page | `/service-fulfillment-policy` | [apps/web/app/service-fulfillment-policy/page.tsx](../../apps/web/app/service-fulfillment-policy/page.tsx) |
| web | page | `/service-guarantee` | [apps/web/app/service-guarantee/page.tsx](../../apps/web/app/service-guarantee/page.tsx) |
| web | page | `/services/[slug]` | [apps/web/app/services/[slug]/page.tsx](../../apps/web/app/services/[slug]/page.tsx) |
| web | page | `/services` | [apps/web/app/services/page.tsx](../../apps/web/app/services/page.tsx) |
| web | page | `/sms-terms` | [apps/web/app/sms-terms/page.tsx](../../apps/web/app/sms-terms/page.tsx) |
| web | page | `/support` | [apps/web/app/support/page.tsx](../../apps/web/app/support/page.tsx) |
| web | page | `/terms` | [apps/web/app/terms/page.tsx](../../apps/web/app/terms/page.tsx) |
| web | page | `/trust` | [apps/web/app/trust/page.tsx](../../apps/web/app/trust/page.tsx) |
| web | page | `/trust-safety` | [apps/web/app/trust-safety/page.tsx](../../apps/web/app/trust-safety/page.tsx) |
| web | page | `/why-breero` | [apps/web/app/why-breero/page.tsx](../../apps/web/app/why-breero/page.tsx) |
| web | page | `/worker` | [apps/web/app/worker/page.tsx](../../apps/web/app/worker/page.tsx) |
| partner | handler | `/health` | [apps/partner/app/health/route.ts](../../apps/partner/app/health/route.ts) |
| partner | page | `/` | [apps/partner/app/page.tsx](../../apps/partner/app/page.tsx) |
| ops | handler | `/health` | [apps/ops/app/health/route.ts](../../apps/ops/app/health/route.ts) |
| ops | page | `/` | [apps/ops/app/page.tsx](../../apps/ops/app/page.tsx) |
| admin | handler | `/health` | [apps/admin/app/health/route.ts](../../apps/admin/app/health/route.ts) |
| admin | page | `/` | [apps/admin/app/page.tsx](../../apps/admin/app/page.tsx) |
