# Final auth exact-head CI

This ordinary repository commit follows the async-auth regression cleanup so the required backend workflows evaluate the completed implementation on the exact review head.

The final source set proves:

- Argon2id password creation and verification run through Starlette's thread pool;
- legacy `pbkdf2_sha256$...` credentials are verified with bounded work and upgraded transactionally;
- every async account-creation path awaits password hashing;
- local access tokens use PyJWT with fixed algorithm, issuer, audience, expiry, issued-at, not-before, subject, and token-ID checks;
- Keycloak signing-key retrieval uses one cached, timeout-bounded client outside the event-loop thread;
- the FastAPI lifespan owns background JWKS refresh and clean shutdown;
- temporary repair scripts and self-modifying workflows are absent from the review diff.

The immediately preceding cleanup commit is `6003f3689787c1e12cdd8fb0333e7157664971c1`. The authoritative acceptance result is the required quality run attached to the commit containing this document update; earlier failed or approval-blocked runs are not acceptance evidence.
