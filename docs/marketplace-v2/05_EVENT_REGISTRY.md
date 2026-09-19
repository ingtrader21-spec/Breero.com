# EVENT REGISTRY

Each event entry defines:

```
event_type

schema_version

producer

aggregate

destinations

payload schema

PII classification

ordering

retry

retention
```

Initial Marketplace registry:

```
project_request.created.v1
project_request.submitted.v1
project_request.qualified.v1
project_request.cancelled.v1

provider_application.submitted.v1
provider.approved.v1
provider.suspended.v1

matching.started.v1
matching.completed.v1

opportunity.sent.v1
opportunity.viewed.v1
opportunity.accepted.v1
opportunity.declined.v1
opportunity.expired.v1

lead.connected.v1

quote.sent.v1
quote.revised.v1
quote.accepted.v1
quote.declined.v1

conversation.message_sent.v1

booking.created.v1
booking.confirmed.v1
booking.cancelled.v1

job.assigned.v1
job.en_route.v1
job.arrived.v1
job.started.v1
job.completed.v1

review.submitted.v1

credential.submitted.v1
credential.verified.v1
credential.expiring.v1
credential.expired.v1
credential.revoked.v1

dispute.created.v1
dispute.resolved.v1

communication.preference_changed.v1
```

Later:

```
payment.captured.v1

payment.refunded.v1

payout.created.v1

payout.paid.v1

subscription.activated.v1

subscription.cancelled.v1
```

---
