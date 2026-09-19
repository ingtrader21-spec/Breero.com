# Capability registry

This records source defaults at the accepted baseline, with the email-guard extension explicitly noted below. The original baseline is documented in [CURRENT_SYSTEM.md](CURRENT_SYSTEM.md), not live environment values. [SOURCE_INVENTORY.json](SOURCE_INVENTORY.json) enumerates the baseline boolean and mode fields in `Settings` and `ObservabilitySettings`. Default flag values are not proof that all related task or transport code honors them.

| Source setting | Default | Effective source behavior / certification gap |
|---|---|---|
| `STRIPE_ENABLED` | false | Stripe payment route mount also requires PAYMENTS_ENABLED |
| `PAYMENTS_ENABLED` | false | Customer payment and payment routes dark by default |
| `ONLINE_CHECKOUT_ENABLED` | false | Public online_payments projection also requires Stripe and payments |
| `PAID_LEADS_ENABLED` | false | Paid-lead route mount also requires Stripe and payments |
| `AUTOMATIC_REFUNDS_ENABLED` | false | Automatic refund intent dark; financial certification remains required |
| `AUTOMATIC_BOOKING_ENABLED` | false | Public instant_booking projection also requires scheduling and automatic confirmation |
| `SCHEDULING_ENABLED` | true | Availability, booking and booking-intent routes mounted; not proof of instant booking |
| `AUTOMATIC_PROVIDER_ASSIGNMENT_ENABLED` | false | Automatic assignment projection false; manual dispatch foundation exists |
| `AUTOMATIC_CONFIRMED_BOOKINGS` | false | Automatic confirmation/instant booking disabled in source configuration |
| `PROVIDER_SELF_SERVICE_ENABLED` | false | Public projection disabled; some provider registration/catalog routes remain mounted, so this is not a universal provider-route kill switch |
| `MARKETPLACE_MATCHING_ENABLED` | false | Public projection disabled; existing dispatch candidates remain a separate foundation |
| `MARKETPLACE_MESSAGING_ENABLED` | false | STUB: projection only; no conversation domain |
| `MARKETPLACE_REVIEWS_ENABLED` | false | STUB: projection only; no verified-review domain |
| `PAYOUT_ENABLED` | false | Finance API route family dark; scheduled earning release and batch creation remain active if beat/worker run |
| `MARKETING_EMAIL_ENABLED` | false | Marketing capability dark; not a universal email delivery guard |
| `MARKETING_SMS_ENABLED` | false | Marketing capability dark; full SMS transport unimplemented |
| `KEYCLOAK_ENABLED` | false | Local JWT path remains executable; canonical production example sets true |
| `GEOCODING_ENABLED` | false | Address/geography public route families excluded; administrative zone routes remain mounted |
| `MIDDLEWARE_ENABLED` | false | Adapter rejects delivery; worker parks/reactivates public-submission CRM events only |
| `ODOO_ENABLED` | false | DEPRECATED: true is rejected at Settings startup in every environment |
| `EMAIL_ENABLED` | false | Required alongside LIVE_EMAIL_DELIVERY and the accepted transactional mode at HTTP/SMTP send boundaries |
| `LIVE_EMAIL_DELIVERY` | false | Added after the baseline snapshot; guards HTTP/SMTP, parks disabled events, and cannot be enabled in production Settings |
| `SMS_ENABLED` | false | SMS configuration setting; fake/unconfigured gateways only |
| `METRICS_ENABLED` | true | Executable `/metrics` exposition, excluded from OpenAPI; ingress must keep it private |
| `OTEL_ENABLED` | false | Optional API/worker instrumentation; true requires configured OTLP endpoint |
| `TRANSACTIONAL_EMAIL_MODE` | `controlled_canary` | HTTP/SMTP require this exact mode plus both email flags; disabled/unknown modes cannot send; no recipient allowlist certification |
| `TRANSACTIONAL_SMS_MODE` | `controlled_canary` | Accepted configuration values are disabled/controlled_canary; no complete SMS transport enforcement exists |

## Transport and frontend switches outside Settings

| Setting / source | Default | Actual boundary |
|---|---|---|
| `EMAIL_DELIVERY_URL` in `app/integrations/email.py` | empty | Nonempty value configures the legacy HTTP destination, subject to all email guards; not a governed Klyrow path |
| `EMAIL_DELIVERY_API_KEY` in the same adapter | empty | Optional HTTP authentication; not an enablement or consent control; value is never inventoried |
| `NEXT_PUBLIC_KEYCLOAK_ENABLED` in `apps/web/lib/keycloak.ts` | false unless exactly `true` | Browser login selection only; backend remains authentication/authorization authority |
| `NEXT_PUBLIC_KEYCLOAK_ISSUER` / `NEXT_PUBLIC_KEYCLOAK_CLIENT_ID` | empty / `breero-web-production` | Browser PKCE configuration; canonical issuer must be supplied at build/deployment |

The email-guard extension supersedes the baseline transport findings above. Missing
HTTP/SMTP configuration and disabled delivery park outbox events rather than
reporting a local no-op as successful delivery. Replay remains explicit and audited;
see [EMAIL_DELIVERY_GUARD.md](../runbooks/EMAIL_DELIVERY_GUARD.md). The generated
SOURCE_INVENTORY.json remains the dated baseline snapshot; it is not an activation
record or a regenerated inventory of this extension.

## Mission names and implementation/activation separation

The mission names `PAYOUTS_ENABLED`, `AUTO_ASSIGN_PROVIDER`, `AUTO_CONFIRM_BOOKING`, `MESSAGING_ENABLED`, `REVIEWS_ENABLED`, `LIVE_SMS_DELIVERY`, `FEATURED_PROVIDERS_ENABLED`, `MARKETING_ENABLED`, and `AI_AUTOMATION_ENABLED` are not existing normalized Settings fields. Absence is not an enforced kill switch. Preserve existing API behavior and introduce reviewed aliases/guards additively in their owning workstreams. No missing commercial or AI capability is authorized for activation.

Production Settings currently reject enabling payments, payouts, paid leads, online checkout, automatic refunds/booking/assignment/confirmation, provider self-service, matching, messaging, reviews or marketing flags. They require scheduling enabled. These restrictions remain in force; this inventory changes none of them. Each activation needs separate staging evidence, monitoring/rollback, independent approval and a production change record.
