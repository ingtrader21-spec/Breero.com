# BREERO Keycloak registration and recovery boundary

BREERO delegates human credential authority to the canonical Codestra Keycloak realm when `keycloak_enabled=true`.

## Public identity flow

The reviewed central Keycloak registration policy declares `breero-portal` as an allowed public self-registration client. The Keycloak realm remains fail closed until the `codestra-registration-gate` is installed and read back as REQUIRED in the protected registration flow.

The `breero-portal` runtime client remains disabled until the exact BREERO callback, post-logout redirect, and web origin are independently verified. No wildcard redirect is authorized.

## Local BREERO behavior

When Keycloak is authoritative, BREERO must reject local:

- account registration;
- login/refresh credential handling;
- password set/change/forgot/reset;
- local email verification and resend flows.

BREERO may bind a verified Keycloak `(issuer, subject)` to its local user and then apply BREERO-owned tenant, vendor, department, role, permission and record-scope policy.

Public signup does not grant staff or administrator privileges. Internal support, dispatch and admin access remains invitation/provisioning and RBAC controlled by BREERO.

## Password recovery

Human recovery is:

```text
Browser -> Keycloak -> Klyrow SECURITY SMTP -> recipient
```

Klyrow/Postal is transport only. Reset tokens, passwords, verification secrets and complete action URLs must not pass through BREERO business APIs, Kong, Middleware, Odoo or n8n.

## Cross-system integration

BREERO business integrations use the governed Middleware boundary. BREERO must not use public Kong as a direct business-service dependency and must not connect directly to Klyrow SMTP for application-owned credential recovery.

## Activation gate

Before enabling the BREERO Keycloak client or realm self-registration, staging must prove:

```text
BREERO_EXACT_REDIRECT_URI=PASS
BREERO_EXACT_POST_LOGOUT_URI=PASS
BREERO_EXACT_WEB_ORIGIN=PASS
BREERO_ALLOWED_REGISTRATION=PASS
BREERO_UNAPPROVED_CLIENT_REGISTRATION=REJECTED
BREERO_LOCAL_REGISTRATION=BLOCKED
BREERO_LOCAL_PASSWORD_RECOVERY=BLOCKED
BREERO_PASSWORD_RESET_EMAIL=PASS
RESET_REPLAY=REJECTED
RESET_MATERIAL_OUTSIDE_KEYCLOAK=ZERO
```

No production activation is authorized by this document.
