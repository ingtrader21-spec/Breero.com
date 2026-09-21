# Breero Keycloak integration

Breero uses the `codestra` realm at `https://auth.codestra.co/realms/codestra`. The API reads the realm discovery document and validates its exact issuer. Authorization uses code flow with PKCE S256, a signed HttpOnly transaction cookie, state, and nonce. Code exchange and ID-token validation happen only in the Breero API. The browser receives Breero's HttpOnly application-session cookies, never Keycloak access or refresh tokens.

## Realm objects

Create dedicated clients `breero-client-web`, `breero-provider-web`, `breero-admin-web`, `breero-api`, and `breero-provisioner`. Web clients use standard flow, client authentication, exact API callback URIs, exact web origins, and no implicit or direct-access-grant flow. `breero-api` represents the API audience. Secrets belong in the deployment secret store and are mounted as files; they must not use `NEXT_PUBLIC_*` variables.

Create realm roles `breero_client`, `breero_provider`, `breero_provider_admin`, `breero_dispatch`, `breero_support`, and `breero_admin`. Keycloak roles authenticate a portal identity; Breero database onboarding, organization membership, ownership, compliance, service area, and capacity remain the authority for marketplace eligibility.

## Provisioner permissions

Enable client authentication and the service account only on `breero-provisioner`. Disable standard, implicit, direct access grant, OAuth device, and service-account flows on all clients except where stated. Through fine-grained realm-management permissions, grant only:

- `query-users` and `view-users` to find/read identities;
- `manage-users` constrained to Breero-managed users for create and approved attribute updates;
- role mapping only for the six `breero_*` roles;
- permission to execute required actions such as verify email and update password.

Do not grant `realm-admin`, client management, realm configuration, identity-provider management, or permissions over unrelated Codestra roles. If the installed Keycloak version cannot constrain `manage-users` sufficiently, treat provisioning as blocked rather than granting realm-admin.

## Cutover

Apply migration `026_keycloak_identity_link` with nullable linkage fields, provision and test clients/roles, backfill users by a reviewed one-time email match, then make `keycloak_subject` mandatory in a later migration after unmatched accounts reach zero. Enable `KEYCLOAK_ENABLED=true` and `BREERO_LOCAL_PASSWORD_AUTH=false` together. Rollback restores the previous application version and leaves the nullable linkage columns intact; do not delete Keycloak users during rollback.

Required settings include `KEYCLOAK_HOST=https://auth.codestra.co`, `KEYCLOAK_REALM=codestra`, `KEYCLOAK_ISSUER`, `KEYCLOAK_AUDIENCE=breero-api`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_CLIENT_SECRET_FILE`, and `KEYCLOAK_REDIRECT_URI`. The verified issuer is `https://auth.codestra.co/realms/codestra`. The former `auth.codestra.agency` identity hostname is deprecated and must not be used by active deployments.
