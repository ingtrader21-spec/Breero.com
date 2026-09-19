# Authentication critical-finding closure

## BE-01 — password hashing

New password hashes use Argon2id through the existing `pwdlib` dependency. Hashing and verification run through Starlette's threadpool so CPU work does not execute on the async request loop. Existing `pbkdf2_sha256$iterations$salt$digest` values remain readable with bounded iteration validation and are replaced with Argon2id in the same successful-login transaction.

## BE-02 — Keycloak signing keys

The process owns one timeout-bounded, caching `PyJWKClient`. Potential network access for signing-key resolution runs off the event loop; PyJWT signature and claim verification remains inline. The FastAPI lifespan refreshes the JWKS cache on a bounded background interval and shutdown stops the refresher. Key-service transport failures return a controlled 503 rather than indefinitely blocking a worker loop.

## BE-03 — local access tokens

Local HS256 tokens are encoded and decoded by PyJWT with the algorithm pinned, fixed issuer and audience validation, and required `exp`, `iat`, `sub`, `iss`, `aud`, `nbf`, and `jti` claims. Already-issued legacy-shape access tokens remain valid for their normal one-hour lifetime through a bounded rolling-deployment compatibility path.

No identity provider, secret, deployment, provider, payout, dialing, or SSH state is changed by this source branch.
