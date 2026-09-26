"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useState } from "react";
import { PageHeader, useAdmin } from "../../../components/AdminShell";
import { ConfirmAction } from "../../../components/ConfirmAction";
import { EffectiveAccessView } from "../../../components/EffectiveAccessView";
import { ErrorMessage, KeyValues, Loading, Notice, Section, StatusBadge } from "../../../components/ui";
import { describeAccessChange, grantsPrivilege, newAssignment, setScope, validateAssignments, validateReason } from "../../../lib/access";
import { formatDateTime, humanize } from "../../../lib/format";
import type { AccessAssignment, AccessRole, AdminUserDetail, Department, EffectiveAccess, TenantScope } from "../../../lib/types";
import { useResource } from "../../../lib/useResource";

export default function UserDetailPage() {
  const params = useParams<{ userId: string }>();
  const userId = params?.userId ?? "";
  const { api } = useAdmin();
  const [detailOverride, setDetailOverride] = useState<AdminUserDetail | null>(null);

  const loadDetail = useCallback(() => api.getUser(userId), [api, userId]);
  const loadAccess = useCallback(() => api.getEffectiveAccess(userId), [api, userId]);
  const loadCatalog = useCallback(() => api.accessCatalog(), [api]);
  const detail = useResource(userId ? loadDetail : null);
  const access = useResource(userId ? loadAccess : null);
  const catalog = useResource(loadCatalog);
  const user = detailOverride ?? detail.data;

  return (
    <>
      <PageHeader eyebrow="Users & access" title={user?.full_name ?? "User"}>
        <p><Link href="/users">← All users</Link></p>
      </PageHeader>
      <Loading active={detail.loading && !user} />
      <ErrorMessage error={detail.error} />
      {user && (
        <>
          <Section title="Account">
            <KeyValues rows={[
              { label: "Email", value: user.email },
              { label: "Status", value: <StatusBadge value={user.status} tone={user.status === "active" ? "success" : "danger"} /> },
              { label: "Account type", value: humanize(user.role) },
              { label: "Email verified", value: user.email_verified ? "Yes" : "No" },
              { label: "Identity authority", value: user.identity_authority === "keycloak" ? "Keycloak" : "Local (Breero)" },
              { label: "Active Breero sessions", value: String(user.active_session_count) },
              { label: "Created", value: formatDateTime(user.created_at) },
              { label: "Updated", value: formatDateTime(user.updated_at) },
            ]} />
            {user.identity_links.length > 0 && (
              <p>Linked identity issuer{user.identity_links.length > 1 ? "s" : ""}: {user.identity_links.map((link) => `${link.issuer} (last seen ${formatDateTime(link.last_seen_at)})`).join("; ")}</p>
            )}
            <LifecycleControls user={user} onChanged={(next) => { setDetailOverride(next); access.reload(); }} />
          </Section>
          <Section title="Effective access">
            <Loading active={access.loading} />
            <ErrorMessage error={access.error} />
            {access.data && <EffectiveAccessView access={access.data} />}
          </Section>
          {access.data && catalog.data && (
            <AccessEditor
              key={access.data.access.assignments.map((item) => `${item.role}:${item.department}:${item.vendor_id ?? ""}:${item.is_primary}`).join("|")}
              userId={user.id}
              current={access.data}
              roles={catalog.data.roles}
              departments={catalog.data.departments}
              scopes={catalog.data.tenant_scopes}
              onSaved={() => { setDetailOverride(null); access.reload(); detail.reload(); }}
            />
          )}
          <ErrorMessage error={catalog.error} />
        </>
      )}
    </>
  );
}

function LifecycleControls({ user, onChanged }: { user: AdminUserDetail; onChanged: (next: AdminUserDetail) => void }) {
  const { api } = useAdmin();
  const authority = user.identity_authority === "keycloak"
    ? "The Keycloak account is not changed; only Breero portal and API access is affected."
    : "Local credentials are not deleted; only Breero portal and API access is affected.";
  return (
    <div className="admin-actions">
      {user.status === "active" ? (
        <ConfirmAction
          label="Disable Breero access"
          title={`Disable ${user.full_name}?`}
          description={`This immediately blocks Breero access, revokes ${user.active_session_count} active Breero session(s) and invalidates issued local tokens. ${authority}`}
          confirmLabel="Disable access"
          tone="danger"
          reasonLabel="Reason (recorded in the audit trail)"
          validateReason={validateReason}
          onConfirm={async (reason) => onChanged(await api.disableUser(user.id, reason))}
        />
      ) : (
        <ConfirmAction
          label="Reactivate Breero access"
          title={`Reactivate ${user.full_name}?`}
          description={`Existing role assignments become effective again. Previously revoked sessions stay revoked, so the user must sign in again. ${authority}`}
          confirmLabel="Reactivate access"
          reasonLabel="Reason (recorded in the audit trail)"
          validateReason={validateReason}
          onConfirm={async (reason) => onChanged(await api.reactivateUser(user.id, reason))}
        />
      )}
    </div>
  );
}

interface EditorProps {
  userId: string;
  current: EffectiveAccess;
  roles: AccessRole[];
  departments: Department[];
  scopes: TenantScope[];
  onSaved: () => void;
}

function AccessEditor({ userId, current, roles, departments, scopes, onSaved }: EditorProps) {
  const { api } = useAdmin();
  const [assignments, setAssignments] = useState<AccessAssignment[]>(current.access.assignments);
  const errors = validateAssignments(assignments);
  const change = describeAccessChange(current.access.assignments, assignments);

  function update(index: number, next: AccessAssignment) {
    setAssignments(assignments.map((item, i) => (i === index ? next : item)));
  }

  return (
    <Section title="Edit role assignments">
      <p>Assignments are Breero-owned access state for brand <strong>{current.brand_key}</strong>. Only a superadmin can grant superadmin or change another administrator.</p>
      {assignments.map((item, index) => (
        <fieldset key={index} className="admin-assignment">
          <legend className="portal-eyebrow">Assignment {index + 1}</legend>
          <label>Role
            <select value={item.role} onChange={(event) => update(index, newAssignment(event.target.value as AccessRole, item.is_primary))}>
              {roles.map((role) => <option key={role} value={role}>{humanize(role)}</option>)}
            </select>
          </label>
          <label>Department
            <select value={item.department} onChange={(event) => update(index, { ...item, department: event.target.value as Department })}>
              {departments.map((department) => <option key={department} value={department}>{humanize(department)}</option>)}
            </select>
          </label>
          <label>Scope
            <select value={item.tenant_scope} onChange={(event) => update(index, setScope(item, event.target.value as TenantScope, item.vendor_id))}>
              {scopes.map((scope) => <option key={scope} value={scope}>{humanize(scope)}</option>)}
            </select>
          </label>
          {item.tenant_scope === "vendor" && (
            <label>Vendor ID<input value={item.vendor_id ?? ""} onChange={(event) => update(index, { ...item, vendor_id: event.target.value.trim() || null })} /></label>
          )}
          <label className="admin-check">
            <input type="radio" name="primary-assignment" checked={item.is_primary} onChange={() => setAssignments(assignments.map((other, i) => ({ ...other, is_primary: i === index })))} />
            Primary
          </label>
          <button type="button" className="admin-button" onClick={() => setAssignments(assignments.filter((_, i) => i !== index))}>Remove</button>
        </fieldset>
      ))}
      <div className="admin-actions">
        <button type="button" className="admin-button" disabled={assignments.length >= 32} onClick={() => setAssignments([...assignments, newAssignment("support", assignments.length === 0)])}>Add assignment</button>
      </div>
      {errors.length > 0 && <Notice tone="danger" title="Fix before saving"><ul>{errors.map((message) => <li key={message}>{message}</li>)}</ul></Notice>}
      {assignments.length === 0 && <Notice tone="warning">Saving with no assignments leaves this account with no access at all.</Notice>}
      {grantsPrivilege(assignments) && <Notice tone="warning">These assignments grant administrator privileges.</Notice>}
      <ConfirmAction
        label="Save access"
        title="Replace this user's access?"
        description={`Added roles: ${change.added.map(humanize).join(", ") || "none"}. Removed roles: ${change.removed.map(humanize).join(", ") || "none"}. The change takes effect on the user's next request.`}
        confirmLabel="Replace access"
        reasonLabel="Reason (recorded in the audit trail)"
        validateReason={validateReason}
        disabled={errors.length > 0}
        onConfirm={async (reason) => {
          await api.replaceAccess(userId, assignments, reason);
          onSaved();
        }}
      />
    </Section>
  );
}
