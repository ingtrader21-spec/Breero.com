"use client";

import { type ChangeEvent, type FormEvent, useState } from "react";

import {
  DataTable,
  formatDate,
  formatLabel,
  PortalConfirmForm,
  PortalEmpty,
  PortalError,
  PortalLoading,
  PortalNotice,
  PortalSection,
  StatusBadge,
  type DataColumn,
  usePortalQuery,
  usePortalSession,
} from "@breero/portal";

import type { AccessCatalog, AccessContext, ListResponse, User } from "./admin-types";

export function UsersPanel() {
  const users = usePortalQuery<ListResponse<User>>("/admin/users?limit=200");
  const catalog = usePortalQuery<AccessCatalog>("/auth/access/catalog");
  const { request } = usePortalSession();
  const [selectedId, setSelectedId] = useState("");
  const access = usePortalQuery<AccessContext>(
    selectedId ? `/auth/access/users/${selectedId}` : null,
  );
  const [role, setRole] = useState("customer");
  const [department, setDepartment] = useState("customer");
  const [tenantScope, setTenantScope] = useState("brand");
  const [vendorId, setVendorId] = useState("");
  const [reviewing, setReviewing] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function saveAccess() {
    if (!selectedId) return;
    setError("");
    try {
      await request<AccessContext>(`/auth/access/users/${selectedId}`, {
        method: "PUT",
        body: JSON.stringify({
          brand_key: "breero",
          assignments: [
            {
              role,
              department,
              tenant_scope: tenantScope,
              vendor_id: vendorId || null,
              is_primary: true,
            },
          ],
        }),
      });
      setMessage("Access assignment replaced and applied.");
      setReviewing(false);
      access.retry();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to update access");
      throw reason;
    }
  }

  const columns: DataColumn<User>[] = [
    {
      key: "user",
      label: "User",
      render: (item) => (
        <span>
          <strong>{item.full_name}</strong>
          <br />
          <small>{item.email}</small>
        </span>
      ),
    },
    { key: "role", label: "Legacy role", render: (item) => <StatusBadge value={item.role} /> },
    {
      key: "active",
      label: "Account",
      compact: true,
      render: (item) => <StatusBadge value={item.is_active ? "active" : "inactive"} />,
    },
    {
      key: "verified",
      label: "Email",
      compact: true,
      render: (item) => <StatusBadge value={item.email_verified ? "verified" : "unverified"} />,
    },
    { key: "created", label: "Created", render: (item) => formatDate(item.created_at) },
    {
      key: "action",
      label: "Action",
      compact: true,
      render: (item) => (
        <button
          type="button"
          className="portal-button"
          onClick={() => {
            setSelectedId(item.id);
            setRole(item.role);
            setReviewing(false);
          }}
        >
          Manage access
        </button>
      ),
    },
  ];

  return (
    <div className="portal-split">
      <PortalSection
        title="Identity directory"
        subtitle="Keycloak remains the identity authority; this table is the BREERO application shadow and access context."
      >
        {message ? (
          <PortalNotice title="Access updated" tone="success">
            {message}
          </PortalNotice>
        ) : null}
        {users.loading ? <PortalLoading label="Loading users" /> : null}
        {users.error ? <PortalError error={users.error} onRetry={users.retry} /> : null}
        {users.data ? (
          <DataTable
            rows={users.data.items}
            columns={columns}
            rowKey={(item) => item.id}
            emptyTitle="No application users are available"
          />
        ) : null}
      </PortalSection>
      <PortalSection
        title="Role assignment"
        subtitle="Replacing assignments is explicit and backend-authorized. Keycloak credentials are not changed here."
      >
        {!selectedId ? (
          <PortalEmpty title="Choose a user" />
        ) : (
          <div className="portal-stack">
            {access.loading ? <PortalLoading label="Loading access context" /> : null}
            {access.error ? <PortalError error={access.error} onRetry={access.retry} /> : null}
            {access.data ? (
              <dl className="portal-definition-grid">
                <div>
                  <dt>Dashboard</dt>
                  <dd>{access.data.dashboard_path}</dd>
                </div>
                <div>
                  <dt>Permissions</dt>
                  <dd>{access.data.permissions.length}</dd>
                </div>
                <div>
                  <dt>Identity mode</dt>
                  <dd>{access.data.identity_mode}</dd>
                </div>
                <div>
                  <dt>Current roles</dt>
                  <dd>{access.data.roles.map(formatLabel).join(", ") || "None"}</dd>
                </div>
              </dl>
            ) : null}
            <form
              className="portal-form-grid"
              onSubmit={(event: FormEvent<HTMLFormElement>) => {
                event.preventDefault();
                setReviewing(true);
              }}
            >
              <label>
                Role
                <select
                  value={role}
                  onChange={(event: ChangeEvent<HTMLSelectElement>) => setRole(event.target.value)}
                >
                  {(catalog.data?.roles ?? []).map((value) => (
                    <option key={value} value={value}>
                      {formatLabel(value)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Department
                <select
                  value={department}
                  onChange={(event: ChangeEvent<HTMLSelectElement>) =>
                    setDepartment(event.target.value)
                  }
                >
                  {(catalog.data?.departments ?? []).map((value) => (
                    <option key={value} value={value}>
                      {formatLabel(value)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Tenant scope
                <select
                  value={tenantScope}
                  onChange={(event: ChangeEvent<HTMLSelectElement>) =>
                    setTenantScope(event.target.value)
                  }
                >
                  {(catalog.data?.tenant_scopes ?? []).map((value) => (
                    <option key={value} value={value}>
                      {formatLabel(value)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Vendor ID (provider roles)
                <input
                  value={vendorId}
                  onChange={(event: ChangeEvent<HTMLInputElement>) => setVendorId(event.target.value)}
                  placeholder="Optional UUID"
                />
              </label>
              {error ? (
                <p className="portal-error portal-form-span" role="alert">
                  {error}
                </p>
              ) : null}
              <div className="portal-form-span">
                <button className="portal-button" type="submit">
                  Review replacement
                </button>
              </div>
            </form>
            {reviewing ? (
              <PortalConfirmForm
                title="Replace primary access assignment"
                description={`This replaces the user's current BREERO assignment with ${formatLabel(role)} in ${formatLabel(department)} at ${formatLabel(tenantScope)} scope.`}
                confirmLabel="Apply access replacement"
                onConfirm={saveAccess}
              />
            ) : null}
          </div>
        )}
      </PortalSection>
    </div>
  );
}
