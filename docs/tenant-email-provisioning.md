# BREERO tenant email provisioning

This document defines the branch-safe implementation contract for per-tenant email domains, senders, credentials, compose requests, outbox delivery and staging certification.

Production credentials are never returned by read APIs. Secret values are accepted only at write time and are persisted as external secret references or one-way fingerprints, never plaintext SMTP/API passwords.

Tenant scopes supported by this slice are BREERO brand scope and provider/vendor scope. Every domain, sender and credential row carries the brand key and optional vendor scope. Authorization is enforced by effective permission plus record scope.

The canonical workflow is:

`login -> portal context -> domain/sender provisioning -> compose -> backend validation -> integration outbox -> delivery worker -> provider adapter -> delivery result/audit`.

No production sending is enabled by this branch. Controlled-canary and disabled release flags remain authoritative.
