import { humanize } from "../lib/format";
import type { EffectiveAccess } from "../lib/types";
import { KeyValues, Notice } from "./ui";

export function EffectiveAccessView({ access }: { access: EffectiveAccess }) {
  return (
    <>
      {access.status === "disabled" && (
        <Notice tone="warning" title="Access suspended">
          This account is disabled. Its assignments are kept for reactivation but grant no permissions while disabled.
        </Notice>
      )}
      {!access.managed_profile && (
        <Notice title="Default access">
          No explicit access profile exists yet, so access is derived from the account type. Saving assignments below creates a managed profile.
        </Notice>
      )}
      <KeyValues rows={[
        { label: "Roles", value: access.access.roles.map(humanize).join(", ") || "None" },
        { label: "Departments", value: access.access.departments.map(humanize).join(", ") || "None" },
        { label: "Dashboard", value: access.access.dashboard_path },
      ]} />
      <h3>Effective permissions ({access.effective_permissions.length})</h3>
      {access.effective_permissions.length ? (
        <ul className="admin-tag-list">{access.effective_permissions.map((permission) => <li key={permission}>{permission}</li>)}</ul>
      ) : <p className="portal-empty">No effective permissions.</p>}
      {access.overrides.length > 0 && (
        <>
          <h3>Permission overrides</h3>
          <div className="portal-table-wrap">
            <table>
              <thead><tr><th>Permission</th><th>Effect</th><th>Source</th></tr></thead>
              <tbody>
                {access.overrides.map((item) => (
                  <tr key={`${item.source}:${item.role ?? ""}:${item.permission}`}>
                    <td>{item.permission}</td>
                    <td>{item.allow ? "Allow" : "Deny"}</td>
                    <td>{item.source === "role" ? `Role: ${humanize(item.role ?? "")}` : "User override"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}
