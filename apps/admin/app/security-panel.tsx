"use client";

import {
  formatDate,
  formatLabel,
  PortalNotice,
  PortalSection,
  usePortalSession,
} from "@breero/portal";

export function SecurityPanel() {
  const { state } = usePortalSession();
  if (state.status !== "authenticated") return null;
  return (
    <div className="portal-stack">
      <PortalSection
        title="Administrative authority"
        subtitle="Resolved by Keycloak identity and backend access assignments."
      >
        <dl className="portal-definition-grid">
          <div>
            <dt>User</dt>
            <dd>{state.session.user.full_name}</dd>
          </div>
          <div>
            <dt>Roles</dt>
            <dd>{state.session.context.roles.map(formatLabel).join(", ")}</dd>
          </div>
          <div>
            <dt>Departments</dt>
            <dd>{state.session.context.departments.map(formatLabel).join(", ")}</dd>
          </div>
          <div>
            <dt>Tenant scope</dt>
            <dd>{state.session.context.assignments[0]?.tenant_scope ?? "None"}</dd>
          </div>
          <div>
            <dt>Permissions</dt>
            <dd>{state.session.context.permissions.length}</dd>
          </div>
          <div>
            <dt>Session expires</dt>
            <dd>{formatDate(new Date(state.session.expires_at * 1000))}</dd>
          </div>
        </dl>
      </PortalSection>
      <PortalNotice title="Finance separation of duties" tone="success">
        Payout reviewers cannot approve the same batch, and approvers cannot submit it. The backend
        rejects those conflicts even when the interface is manipulated.
      </PortalNotice>
      <PortalNotice title="Identity authority" tone="info">
        Keycloak remains the source of sign-in identity. BREERO stores role, department, permission,
        and tenant-scope assignments against the synchronized user shadow.
      </PortalNotice>
    </div>
  );
}
