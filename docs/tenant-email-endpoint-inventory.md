# Tenant email endpoint inventory

Planned endpoint groups for the tenant-email slice:

- `/api/v1/email/domains`
- `/api/v1/email/senders`
- `/api/v1/email/credentials`
- `/api/v1/email/messages`
- `/api/v1/email/outbox`

All endpoints require authenticated portal context, fine-grained permissions and tenant record scope. Credential reads return metadata only and never return secret material.
