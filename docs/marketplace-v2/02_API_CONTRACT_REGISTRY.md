# API CONTRACT REGISTRY

Every V2 operation must contain one row.

Template:

| Field              | Value |
| ------------------ | ---- |
| Domain             | <br> |
| Method             | <br> |
| Path               | <br> |
| Operation ID       | <br> |
| Request DTO        | <br> |
| Response DTO       | <br> |
| Principal          | <br> |
| Permission         | <br> |
| Record predicate   | <br> |
| Capability         | <br> |
| Idempotency        | <br> |
| If-Match/version   | <br> |
| State transition   | <br> |
| Audit action       | <br> |
| Outbox event       | <br> |
| Rate limit         | <br> |
| PII classification | <br> |
| 400                | <br> |
| 401                | <br> |
| 403                | <br> |
| 404                | <br> |
| 409                | <br> |
| 412                | <br> |
| 422                | <br> |
| 429                | <br> |
| 503                | <br> |

Example:

| Field            | Value                                   |
| ---------------- | --------------------------------------- |
| Domain           | Quote                                   |
| Method           | POST                                    |
| Path             | `/api/v2/quotes/{quote_id}/accept`      |
| Operation ID     | `acceptQuote`                           |
| Principal        | Customer                                |
| Permission       | `quote.accept`                          |
| Record predicate | originating request belongs to customer |
| Capability       | `quotes`                                |
| Idempotency      | Required                                |
| If-Match         | Required                                |
| State            | `SENT → ACCEPTED`                       |
| Audit            | `QUOTE_ACCEPTED`                        |
| Event            | `quote.accepted.v1`                     |
| PII              | provider/customer-safe projection       |

No endpoint is complete without a registry entry.

## Durable-inbox replay operation

| Field            | Value                                                        |
| ---------------- | ------------------------------------------------------------ |
| Domain           | Integration operations                                       |
| Method           | POST                                                         |
| Path             | `/api/v2/ops/integration-inbox/{id}/replay`                  |
| Operation ID     | `replayIntegrationInboxEvent`                                |
| Principal        | Authorized operations principal                              |
| Permission       | `integration.replay`                                         |
| Record predicate | Tenant-scoped terminal/replayable inbox record               |
| Capability       | Integration enabled and replay permitted                     |
| Idempotency      | Required                                                     |
| Audit            | Reason, actor, source inbox ID, correlation ID, and result   |
| State            | Original history immutable; create a new token-guarded claim |

`integration.retry` does not satisfy this operation.

---
