"use client";

import Link from "next/link";
import { useCallback, useState, type FormEvent } from "react";
import { PageHeader, useAdmin } from "../../components/AdminShell";
import { Empty, ErrorMessage, Loading, Pager, Section, StatusBadge } from "../../components/ui";
import { formatDateTime, humanize } from "../../lib/format";
import type { AccessRole, AdminUserStatus, UserRole } from "../../lib/types";
import { useResource } from "../../lib/useResource";

const ACCESS_ROLES: AccessRole[] = ["customer", "vendor_admin", "technician", "operations", "ops_manager", "support", "finance", "quality", "trust_safety", "sales", "marketing", "admin", "superadmin"];
const USER_ROLES: UserRole[] = ["customer", "vendor_admin", "technician", "operations", "finance", "admin"];
const PAGE_SIZE = 25;

interface Filters { q: string; status: "" | AdminUserStatus; role: "" | UserRole; access_role: "" | AccessRole }

export default function UsersPage() {
  const { api } = useAdmin();
  const [draft, setDraft] = useState<Filters>({ q: "", status: "", role: "", access_role: "" });
  const [filters, setFilters] = useState<Filters>(draft);
  const [page, setPage] = useState(1);

  const loader = useCallback(
    () => api.listUsers({
      q: filters.q.trim() || undefined,
      status: filters.status || undefined,
      role: filters.role || undefined,
      access_role: filters.access_role || undefined,
      page,
      page_size: PAGE_SIZE,
    }),
    [api, filters, page],
  );
  const { data, error, loading } = useResource(loader);

  function search(event: FormEvent) {
    event.preventDefault();
    setPage(1);
    setFilters(draft);
  }

  return (
    <>
      <PageHeader eyebrow="Administration" title="Users & access" />
      <Section title="Search users">
        <form className="admin-form admin-form--inline" onSubmit={search} role="search">
          <label>Name or email<input type="search" value={draft.q} maxLength={160} onChange={(event) => setDraft({ ...draft, q: event.target.value })} /></label>
          <label>Status
            <select value={draft.status} onChange={(event) => setDraft({ ...draft, status: event.target.value as Filters["status"] })}>
              <option value="">Any</option><option value="active">Active</option><option value="disabled">Disabled</option>
            </select>
          </label>
          <label>Account type
            <select value={draft.role} onChange={(event) => setDraft({ ...draft, role: event.target.value as Filters["role"] })}>
              <option value="">Any</option>
              {USER_ROLES.map((role) => <option key={role} value={role}>{humanize(role)}</option>)}
            </select>
          </label>
          <label>Access role
            <select value={draft.access_role} onChange={(event) => setDraft({ ...draft, access_role: event.target.value as Filters["access_role"] })}>
              <option value="">Any</option>
              {ACCESS_ROLES.map((role) => <option key={role} value={role}>{humanize(role)}</option>)}
            </select>
          </label>
          <button type="submit" className="admin-button admin-button--primary">Search</button>
        </form>
        <Loading active={loading} />
        <ErrorMessage error={error} />
        {data && data.items.length === 0 && <Empty>No users match these filters.</Empty>}
        {data && data.items.length > 0 && (
          <>
            <div className="portal-table-wrap">
              <table>
                <thead><tr><th>Name</th><th>Email</th><th>Account type</th><th>Status</th><th>Identity</th><th>Created</th></tr></thead>
                <tbody>
                  {data.items.map((user) => (
                    <tr key={user.id}>
                      <td><Link href={`/users/${user.id}`}>{user.full_name}</Link></td>
                      <td>{user.email}</td>
                      <td>{humanize(user.role)}</td>
                      <td><StatusBadge value={user.status} tone={user.status === "active" ? "success" : "danger"} /></td>
                      <td>{user.identity_linked ? "Linked" : "Not linked"}</td>
                      <td>{formatDateTime(user.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
          </>
        )}
      </Section>
    </>
  );
}
