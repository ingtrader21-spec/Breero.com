# BREERO Marketplace V2 — Threat Model

## Status

Binding security companion for Marketplace V2. This document identifies the minimum threat set that implementation, tests, monitoring, incident response, and launch evidence must address.

It does not claim that every control is implemented. Missing implementation or current evidence remains a production blocker.

## Security objectives

BREERO must protect:

- customer identities, addresses, requests, conversations, bookings, job history, documents and payment-related data;
- provider businesses, memberships, workers, credentials, compensation and payout information;
- administrative and financial authority;
- marketplace state and workflow correctness;
- integration credentials and provider callbacks;
- audit, financial journal and reconciliation evidence;
- release artifacts, configuration and software supply chain.

## Trust boundaries

```text
Browser / external client
        ↓
Caddy / edge / Kong where applicable
        ↓
BREERO API
        ↓
Authentication + Principal + authorization/policy
        ↓
Domain commands + PostgreSQL/PostGIS
        ↓
Audit / idempotency / outbox
        ↓
Workers / adapters
        ↓
Codestra/Kong/middleware + providers

External provider
        ↓
Webhook authentication/signature
        ↓
Durable inbox
        ↓
Worker + translator
        ↓
Authorized domain command
```

Odoo, n8n, Codestra/middleware, Klyrow, Telnexa, Redis, object storage and payment/payout providers are outside the authoritative BREERO domain boundary.

## Threat register

| Threat | Asset | Attacker | Attack path | Required controls | Detection | Response | Residual risk |
|---|---|---|---|---|---|---|---|
| Customer account takeover | Customer account, requests, addresses, conversations, bookings | Credential thief, phisher, malware operator | Stolen session/token, credential stuffing, compromised email/device | OIDC/PKCE, secure session model, MFA where appropriate, short-lived tokens, rate limiting, session revocation, re-auth for high-risk actions | Login anomaly, impossible travel/device anomaly where available, rate-limit events, session changes | Revoke sessions, reset credentials, contain exposed records, investigate audit trail | Compromised endpoint/device may still expose active session |
| Provider owner/manager takeover | Provider account, workers, quotes, credentials, payout settings | Credential thief, insider | Stolen session/token, phishing, weak recovery | OIDC, strong role separation, MFA/re-auth, dual control for financial destination changes, no silent impersonation | Privilege changes, payout destination changes, unusual exports/actions | Freeze provider financial actions, revoke sessions, restore approved configuration | Legitimate-looking actions from compromised principal |
| Worker account takeover | Assigned jobs, customer address/contact, evidence | Credential thief | Stolen worker session/device | Least privilege, assigned-job scoping, short session, remote revocation, device/session controls | Access to unassigned jobs, unusual geolocation/activity | Revoke session, reassign job, investigate customer exposure | Temporary exposure of assigned-job data |
| Cross-customer data access | Customer private data | Authenticated malicious customer | IDOR, weak repository filters, predictable IDs | Ownership-scoped queries, negative authorization tests, 404 masking where appropriate, UUIDs, policy layer | Repeated denied IDs, IDOR probes, cross-scope test telemetry | Block actor/IP, investigate, notify security | Application authorization defect remains high impact |
| Cross-provider data access | Provider opportunities, quotes, jobs, customers, financials | Malicious provider member | IDOR, tenant scope omission | Provider membership scoping, tenant/provider query filters, policy layer, optional RLS defense-in-depth | Deny telemetry, unusual resource enumeration | Suspend actor/provider, investigate data exposure | Complex membership changes can create edge cases |
| Admin privilege escalation | Admin/finance/security authority | Internal or compromised lower-privilege user | Role misconfiguration, insecure admin endpoint, privilege chaining | Explicit permissions, no wildcard admin, dual control, break-glass, separation of duties, admin route tests | Permission-change audit, unexpected role grants, privileged action alerts | Revoke elevation, freeze critical capabilities, incident review | Authorized insider with collusion remains possible |
| OIDC token/session theft | User/machine identity | External attacker, malware, compromised browser | XSS, log leak, proxy leak, local storage theft, redirect abuse | BFF/HttpOnly session preferred, CSP, no token logs, secure cookies, PKCE, strict redirect URIs, short TTL, issuer/audience validation | Token reuse anomalies, invalid issuer/audience, unusual session activity | Revoke session/client, rotate credentials, patch client issue | Active stolen token valid until revoked/expired |
| Webhook forgery | Marketplace state | External attacker | Fake POST to webhook endpoint | Provider signature/auth, raw-body verification, allowlisted contract, no business mutation before verification | Invalid signature counter, source anomaly | Reject, rate limit, block source, alert on burst | Provider credential/key compromise can bypass signature check |
| Webhook replay | Duplicate side effects | External attacker or duplicate provider delivery | Reusing valid signed event | Timestamp window, unique external event ID, request hash, durable inbox uniqueness, idempotent command | Duplicate inbox metrics, replay rejection | Ignore safely, investigate repeated attack pattern | Provider may legitimately retry ambiguous delivery |
| Provider credential theft | External integrations | Attacker, insider, compromised host | Git/image/log leak, filesystem theft, overbroad secret access | Secret manager/KMS, scoped credentials, rotation inventory, no secrets in Git/images/logs/frontend, short-lived machine identity where possible | Secret scan, auth anomalies, provider alerts | Revoke/rotate, disable provider capability, incident response | Some providers require long-lived credentials |
| Malicious document upload | API/workers/users | Malicious customer/provider | Executable disguised as PDF/image, parser exploit, archive bomb | Extension allowlist, MIME/magic validation, size/page/decompression limits, malware scan, quarantine, safe parser, private storage | Scanner detections, parser failures, quarantine metrics | Quarantine/delete, block uploader, patch parser if needed | Zero-day parser/scanner bypass |
| PII exfiltration | Customer/provider private data | Insider, compromised admin, malicious integration | Bulk export, logs, CRM projection, API scraping, backup theft | Classification policy, export permissions, least privilege, projection rules, encryption, rate limits, audit, secure backups | Export audit, unusual query volume, DLP/provider logs where available | Revoke access, preserve evidence, incident/legal response | Authorized users may still misuse permitted access |
| Insider abuse | All sensitive assets | Employee/contractor with legitimate access | Misuse of admin/support/export/break-glass | Least privilege, dual control, just-in-time elevation, support impersonation policy, immutable audit, export controls | Privileged-action alerts, audit review, unusual access patterns | Revoke account, freeze affected capability, investigate | Collusion or deliberate low-and-slow abuse |
| Fraudulent payment/refund | Customer funds, BREERO funds | Compromised finance/admin account or malicious integration | Unauthorized capture/refund, manipulated amount | Capability gates, explicit permissions, dual control where required, idempotency, immutable journal, provider-authoritative callback, reconciliation | Amount/state mismatch, unusual finance actions, provider statement differences | Freeze payments/refunds, reconcile, reverse where supported | Provider dispute/chargeback risk remains external |
| Fraudulent payout | Provider funds | Compromised provider/admin/finance actor | Change payout destination, approve/submit unauthorized payout | Separate finance permissions, dual control, destination-change cooling/re-auth, idempotency, payout journal, reconciliation | Destination changes, payout anomalies, reconciliation mismatch | Freeze payouts, contact provider/payment partner, rotate credentials | Irreversible transfer after provider settlement |
| Duplicate payment/refund/payout | Financial correctness | Retry storm, worker race, provider ambiguity | Automatic retry after uncertain result | Operation retry classification, idempotency keys, unique constraints, reconciliation-required state, no blind retry | Duplicate external IDs, journal mismatch, provider reconciliation | Stop retries, reconcile provider, create compensating entry if required | Provider idempotency defects or delayed callbacks |
| Duplicate marketplace side effect | Opportunity/lead/booking/job state | Client retry, worker race | Repeated command/webhook delivery | Generic idempotency, optimistic concurrency, partial unique indexes, transaction atomicity | Duplicate-key/conflict metrics | Return original result or reject conflict | Poorly defined external provider semantics |
| Odoo compromise | CRM projection, agent workflow | Attacker controlling Odoo/account | Forged callbacks, direct attempts to mutate marketplace truth | Odoo never authoritative, scoped integration credentials, webhook auth, inbox, command authorization, restricted projections | Invalid Odoo events, unexpected commands, projection drift | Disable Odoo integration, queue projections, rotate credentials | CRM data itself may be exposed |
| n8n compromise | Automation workflows | Attacker controlling n8n | Unapproved workflow calls, secret theft, direct DB attempt | Allowlisted workflows, no direct business-table writes, machine auth, command APIs only, capability gates | Unknown workflow ID, denied command, unusual traffic | Disable n8n capability/credentials, preserve queue | n8n may still expose data it legitimately receives |
| Codestra/Kong/middleware compromise | Integration transport | Attacker controlling middleware/gateway | Forged machine calls, rerouted events, credential abuse | mTLS/client credentials where approved, issuer/audience checks, destination allowlist, command authorization, no authority transfer | Auth failures, unexpected route/destination, signature mismatch | Disable machine client/routes, rotate secrets/certs, queue outbox | Compromised trusted transport can cause broad availability impact |
| Redis compromise | Cache, rate limits, queues, circuit state | Network attacker, compromised host | Public exposure, weak auth, command execution | Private network only, auth/TLS where appropriate, no authoritative business truth, container/network hardening | Connection anomaly, config drift, queue corruption | Isolate/replace Redis, rebuild derived state, pause workers if needed | Availability and replay/rate-limit disruption |
| Object storage exposure | Uploaded evidence/documents | Cloud/storage attacker, misconfiguration | Public bucket/container, leaked signed URL/key | Private ACL, least-privilege service identity, short-lived URLs, encryption, classification, access audit | Public-access scanner, storage logs, unusual downloads | Revoke keys/URLs, close ACL, investigate affected objects | Signed URL may be shared during TTL |
| Database credential theft | Authoritative state | Attacker/insider | Secret leak, host compromise | Secret manager, separate roles, no superuser runtime, rotation, network isolation, TLS where required | Login anomaly, privilege changes, secret scan | Rotate, isolate DB, revoke sessions, restore if tampered | Database access can expose broad state before detection |
| Supply-chain compromise | Source/build/release | Malicious dependency, compromised CI/account | Dependency typosquat, mutable base image, CI token abuse | Lockfiles, pinned images/digests, dependency audit, SBOM, provenance/signature, protected branches, least-privilege CI | Dependency alerts, signature mismatch, reproducibility drift | Block release, rotate CI credentials, rebuild from clean source | Unknown upstream compromise before disclosure |
| Audit tampering | Evidence, incident/reconciliation history | Insider or compromised app | UPDATE/DELETE audit rows | Insert-only permissions, immutable archive/hash chain where used, separate backup | Hash mismatch, missing sequence, DB privilege audit | Preserve snapshots, investigate DB/admin access | DB owner-level attacker may still alter primary storage |
| Release/configuration substitution | Production integrity | Insider, compromised CI/CD | Deploy different image/config than certified | Same artifact promotion, digest pinning, config hash, launch approval bound to exact candidate, provenance/signature | Digest/config mismatch, deploy-policy failure | Abort/rollback deployment, investigate release path | Emergency manual infrastructure action remains a risk |

## Mandatory security tests

At minimum, automated suites must prove:

- wrong/legacy issuer, wrong audience, expired/not-yet-valid/malformed token rejection;
- cross-customer and cross-provider denial;
- worker denial for unassigned jobs;
- dispatcher denial for finance actions;
- support denial for credential verification unless explicitly permitted;
- duplicate idempotency-key behavior under concurrency;
- stale `If-Match` behavior;
- forged, stale and duplicate webhook behavior;
- outbox stale-claim finalization denial;
- upload type/magic mismatch rejection;
- export permission enforcement;
- audit update/delete denial using runtime DB roles;
- break-glass expiry and audit behavior;
- financial replay/retry controls before any live financial capability.

## Incident linkage

Each HIGH-impact threat must map to an on-call runbook before production activation. Security evidence must identify the exact source SHA, image digest, migration head and configuration snapshot it proves.