"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { PageHeader, useAdmin } from "../../components/AdminShell";
import { Empty, ErrorMessage, Loading, Pager, Section, StatusBadge } from "../../components/ui";
import { formatDateTime, humanize } from "../../lib/format";
import { APPLICATION_STATUS_TONE } from "../../lib/providers";
import type { ProviderApplicationStatus } from "../../lib/types";
import { useResource } from "../../lib/useResource";

const STATUSES: ProviderApplicationStatus[] = ["PENDING", "INFORMATION_REQUESTED", "APPROVED", "REJECTED", "DRAFT"];
const PAGE_SIZE = 50;

function displayName(business: Record<string, unknown>, identity: Record<string, unknown>): string {
  const candidates = [business.display_name, business.legal_name, identity.full_name];
  const name = candidates.find((value): value is string => typeof value === "string" && value.trim().length > 0);
  return name ?? "Unnamed provider";
}

export default function ProviderApplicationsPage() {
  const { api } = useAdmin();
  const [status, setStatus] = useState<"" | ProviderApplicationStatus>("PENDING");
  const [page, setPage] = useState(1);
  const loader = useCallback(
    () => api.listApplications({ status: status || undefined, limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE }),
    [api, status, page],
  );
  const { data, error, loading } = useResource(loader);

  return (
    <>
      <PageHeader eyebrow="Administration" title="Provider applications" />
      <Section
        title="Review queue"
        actions={(
          <label className="admin-form">Status
            <select value={status} onChange={(event) => { setPage(1); setStatus(event.target.value as typeof status); }}>
              <option value="">All</option>
              {STATUSES.map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
            </select>
          </label>
        )}
      >
        <p>Decisions are accepted only while an application is pending review.</p>
        <Loading active={loading} />
        <ErrorMessage error={error} />
        {data && data.items.length === 0 && <Empty>No applications in this state.</Empty>}
        {data && data.items.length > 0 && (
          <>
            <div className="portal-table-wrap">
              <table>
                <thead><tr><th>Provider</th><th>Status</th><th>Submitted</th><th>Decided</th><th>Services</th><th>Postal codes</th></tr></thead>
                <tbody>
                  {data.items.map((application) => (
                    <tr key={application.id}>
                      <td><Link href={`/providers/${application.id}`}>{displayName(application.business, application.identity)}</Link></td>
                      <td><StatusBadge value={application.status} tone={APPLICATION_STATUS_TONE[application.status]} /></td>
                      <td>{formatDateTime(application.submitted_at)}</td>
                      <td>{formatDateTime(application.decided_at)}</td>
                      <td>{application.services.length}</td>
                      <td>{application.postal_codes.length}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} />
          </>
        )}
      </Section>
    </>
  );
}
