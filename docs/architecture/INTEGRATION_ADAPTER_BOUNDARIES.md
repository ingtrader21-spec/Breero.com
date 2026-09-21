# Integration Adapter Boundaries

BREERO’s provider-neutral integration contracts live in one module:

```text
apps/api/app/integrations/contracts.py
```

Concrete adapters may implement those contracts, but they must not redefine them. This prevents Stripe, Geoapify, SMTP, SMS, Odoo, middleware, or a future payout provider from becoming the owner of application-facing interfaces.

## Contract authority

The shared boundary owns:

```text
PaymentProvider
PayoutGateway
GeocodingGateway
EmailGateway
SmsGateway
CrmEventDeliveryGateway
IntegrationNotConfigured
GeocodedAddress
TransferResult
EventDeliveryError
EventDeliveryResult
```

Existing imports from provider modules remain compatibility exports during migration. New domain/application code must import contracts from `app.integrations.contracts`, while API routes, workers, and composition factories may select concrete providers.

## Canonical CRM envelope

Odoo and Codestra middleware now share:

```text
apps/api/app/integrations/event_envelope.py
```

The middleware adapter no longer imports `OdooAdapter` to construct an envelope. Provider selection and transport behavior remain separate:

```text
canonical event -> delivery contract -> Odoo adapter OR middleware adapter
```

## Safety rules

- no generic Odoo model-write API may be exposed;
- provider credentials remain inside the concrete adapter;
- external calls do not own BREERO transactions;
- idempotency is stable across retries;
- transient and terminal delivery failures remain distinguishable;
- disabled/unconfigured providers fail closed;
- fake adapters remain available for deterministic unit and failure tests;
- compatibility exports may be removed only after all callers migrate.

## Follow-on migration

This structural PR establishes the contract authority. Later focused branches must move each remaining domain import to the neutral contracts/composition boundary and prove behavior with provider failure, timeout, replay, duplicate-delivery, and recovery tests.

No provider is enabled and no external message, payment, payout, CRM write, or middleware delivery is performed by this refactor.
