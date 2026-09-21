# Capability registry

Generated from source defaults at `ee79c3cb0bd667c3456dd20521563017b7d2d246`. Defaults describe code/configuration only; they are not production activation evidence.

| Source setting | Default | Source |
|---|---|---|
| `AUTOMATIC_BOOKING_ENABLED` | `False` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `AUTOMATIC_CONFIRMED_BOOKINGS` | `False` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `AUTOMATIC_PROVIDER_ASSIGNMENT_ENABLED` | `False` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `AUTOMATIC_REFUNDS_ENABLED` | `False` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `AUTO_ASSIGN_PROVIDER` | `False` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `AUTO_CONFIRM_BOOKING` | `False` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `BREERO_LOCAL_PASSWORD_AUTH` | `True` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `EMAIL_ENABLED` | `False` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `GEOCODING_ENABLED` | `False` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `KEYCLOAK_ENABLED` | `False` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `KEYCLOAK_PROVISIONING_ENABLED` | `False` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `LIVE_CALLBACKS` | `False` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `LIVE_EMAIL_DELIVERY` | `False` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `LIVE_PROVIDER_DISPATCH` | `False` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `LIVE_SMS_DELIVERY` | `False` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `MARKETING_EMAIL_ENABLED` | `False` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `MARKETING_SMS_ENABLED` | `False` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `MARKETPLACE_MATCHING_ENABLED` | `False` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `MARKETPLACE_MESSAGING_ENABLED` | `False` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `MARKETPLACE_REVIEWS_ENABLED` | `False` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `METRICS_ENABLED` | `True` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `MIDDLEWARE_ENABLED` | `False` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `ODOO_DELIVERY_ENABLED` | `False` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `ODOO_ENABLED` | `False` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `ODOO_WRITE_ENABLED` | `False` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `ONLINE_CHECKOUT_ENABLED` | `False` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `OTEL_ENABLED` | `False` | [apps/api/app/observability.py](../../apps/api/app/observability.py) |
| `PAID_LEADS_ENABLED` | `False` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `PAYMENTS_ENABLED` | `False` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `PAYOUT_ENABLED` | `False` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `PROVIDER_ASSIGNMENT_MODE` | `MANUAL` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `PROVIDER_SELF_SERVICE_ENABLED` | `False` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `PUBLIC_BOOKING_API_ENABLED` | `False` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `SCHEDULING_ENABLED` | `True` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `SMS_ENABLED` | `False` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `STRIPE_ENABLED` | `False` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `TRANSACTIONAL_EMAIL_MODE` | `controlled_canary` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |
| `TRANSACTIONAL_SMS_MODE` | `controlled_canary` | [apps/api/app/settings/model.py](../../apps/api/app/settings/model.py) |

## Activation rule

Adding a route, migration, provider credential, or environment variable does not activate a protected capability. Production activation remains a separate M30 decision after staging, security, rollback and monitoring evidence.
