# Admin audit console (isolated feature)

Route: `/audit` (`apps/admin/app/audit/page.tsx`). All code lives in this folder so the
rest of `apps/admin` can evolve independently.

- API: `GET /api/v1/admin/audit/{events,security-events,events/{id},correlations/{id},catalog}`,
  permission `admin.audit.read` (see `docs/audit-read-model.md`).
- Session: reuses the `@breero/portal` session in `sessionStorage`. The token is only sent
  as a bearer header to the `https` API origin, with `credentials: "omit"`.
- Rendering: text only. Metadata comes from the server allowlist and is never parsed as
  HTML or serialized from nested objects.

Hand-offs:

- **Shared client (Agent 5):** `types.ts` and `api.ts` are local stand-ins. When
  `@breero/api-client` exposes the five audit operations and the `AuditEvent*`,
  `AuditCorrelationTrace` and `AuditCatalog` schemas, replace them and delete the stand-ins.
- **Admin navigation (Agent 3):** the "Audit log" section in `app/page.tsx` still says the
  API is not exposed. Link it to `/audit` instead.
