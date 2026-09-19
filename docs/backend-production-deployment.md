# Backend production deployment

Production is defined by the root `docker-compose.production.yml` (Compose project `breero`):
`postgres`, `redis`, `api`, `worker`, and `scheduler` services on the internal `breero_private`
network (Docker network name `breero_breero_private`); only the API additionally joins the shared
`caddy_shared` proxy edge network. Compose assigns default container names (`breero-api-1`,
`breero-worker-1`, `breero-postgres-1`, `breero-redis-1`, `breero-scheduler-1`) since the file sets
no `container_name` overrides. PostgreSQL, Redis and port 8000 have no host publication.

`deploy/production/docker-compose.backend.yml` is a service-free compatibility entry point for the
protected CI workflow. It includes the root manifest and supplies only inert interpolation fixtures
from `deploy/production/compose-validation.env`. It is not a second deployment topology and must
not be used by operators.

Required sequence:

1. Verify at least 15% host disk headroom, exact-head green CI, and production-only secrets.
2. Create a checksum-recorded backup and restore it into an isolated verification database.
3. Start immutable `breero-api:<git-sha>` services without a public Caddy route.
4. Migrate to `012_service_area_dimensions`, seed the production launch catalog, and verify zero
   active fixture/Berlin services through the internal API.
5. Run live/ready, OpenAPI, auth and persisted-intake canaries. Certify geocoding and Stripe when
   booking depends on them.
6. Back up Caddy, replace only the `api.breero.com` maintenance handler, validate, and gracefully
   reload.

Rollback is a single Caddy upstream reversal to maintenance or the previous healthy API. Do not
point production at staging and do not roll the database back during immediate application rollback.

For Geoapify certification, store the production API key in a root-owned file with mode `0600`, set
`GEOAPIFY_API_KEY_REFERENCE` to that absolute path, and keep
`GEOCODING_API_KEY_FILE=/run/secrets/breero_geoapify_api_key`. Set `GEOCODING_ENABLED=true` only
after the rendered Compose configuration shows the secret mounted in the API and worker. Recreate
those two services, confirm `/api/v1/addresses/validate` appears in OpenAPI, and canary a known U.S.
address without logging the key or the full customer address. A rejected credential, ambiguous
result, missing time zone, or provider outage must fail to manual review rather than establish
service coverage.

Middleware delivery remains disabled during the production stack's normal startup. After staging
certification and production activation approval, ensure `breero_middleware_egress` exists using the
same explicit `10.251.12.0/24` creation command documented for staging. Set the four
`BREERO_PROD_MIDDLEWARE_*_FILE` variables to distinct production, root-owned files and apply
`docker-compose.middleware.yml` as a second Compose file. Validate the combined render before
recreating only the `worker` service (`breero-worker-1`). Do not copy staging HMAC or mTLS
credentials into production.
