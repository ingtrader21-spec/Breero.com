# BREERO authentication

BREERO uses one `users` identity table for clients, provider users, dispatch, support, and administrators. Emails are normalized to lowercase and protected by a unique index. Passwords use Argon2; legacy PBKDF2 hashes remain verifiable only for migration.

Access JWTs are short lived and include the credential version. Opaque refresh tokens are stored only as SHA-256 hashes in `auth_sessions`. Refresh rotates the token and reuse revokes the entire token family. Password change/reset increments the credential version and revokes active sessions. Logout revokes the supplied refresh session server-side.

Public client and provider registration are rate limited. Provider registration creates a pending vendor and inactive professional, services, and coverage. Internal accounts are created only by `BREERO_ADMIN` through `POST /api/v1/admin/users` and require initial password setup.

Password reset and email/phone verification use expiring hashed challenges. Delivery remains an outbox concern and all live delivery flags default off.
