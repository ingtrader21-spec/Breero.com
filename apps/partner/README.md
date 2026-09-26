# BREERO Partner Portal

Target: `partners.breero.com`

Provider self-service application. Every screen reads and writes the live BREERO API
under `/api/v1/provider/**`; the provider organization is always derived from the
signed-in principal and no screen sends a vendor identifier.

| Screen | API |
| --- | --- |
| Onboarding wizard (draft/save/submit, status, information requested, rejected, approved) | `GET/PATCH /provider/onboarding`, `GET /provider/onboarding/checklist`, `POST /provider/onboarding/submit` |
| Company profile | `GET/PATCH /provider/profile` |
| Services | `GET /services`, `GET/POST /provider/services`, `PATCH/DELETE /provider/services/{id}` |
| Skills | `GET /provider/skill-catalog`, `GET/POST /provider/skills`, `DELETE /provider/skills/{id}` |
| Team | `GET/POST /provider/workers` |
| Availability (weekly windows, blackouts, 7-day preview) | `/provider/availability/**` |
| Qualifications (metadata + review status; uploads fail closed) | `/provider/qualifications/**` |
| Jobs & offers | `GET /provider/jobs`, `GET /provider/offers`, `POST /provider/offers/{id}/decision`, `GET /provider/leads` (read-only, when enabled) |
| Earnings & payouts | Integration point only — owned by the finance backend |

Versioned mutations send `If-Match` with the version that was loaded; a `409
VERSION_CONFLICT` reloads the record instead of overwriting newer work.

Configuration: `NEXT_PUBLIC_API_BASE_URL` must be an `https://` origin including `/api/v1`.

Checks: `pnpm --filter @breero/partner lint`, `typecheck`, `test`, `build`.
