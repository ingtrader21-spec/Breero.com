"use client";

import {
  DataTable,
  formatDate,
  formatLabel,
  PortalError,
  PortalLoading,
  PortalSection,
  type DataColumn,
  usePortalQuery,
} from "@breero/portal";

import type { AuditEvent, ListResponse } from "./admin-types";

export function AuditTable({ events }: { events: AuditEvent[] }) {
  const columns: DataColumn<AuditEvent>[] = [
    { key: "time", label: "Time", render: (item) => formatDate(item.created_at) },
    {
      key: "action",
      label: "Action",
      render: (item) => <strong>{formatLabel(item.action)}</strong>,
    },
    {
      key: "resource",
      label: "Resource",
      render: (item) => (
        <span>
          <span>{formatLabel(item.resource_type)}</span>
          <br />
          <small className="portal-code">{item.resource_id}</small>
        </span>
      ),
    },
    {
      key: "actor",
      label: "Actor",
      render: (item) => <span className="portal-code">{item.actor_id ?? item.actor_type}</span>,
    },
  ];
  return (
    <DataTable
      rows={events}
      columns={columns}
      rowKey={(item) => item.id}
      emptyTitle="No audit evidence is available"
    />
  );
}

export function AuditPanel() {
  const audit = usePortalQuery<ListResponse<AuditEvent>>("/portal/admin/audit?limit=500");
  return (
    <PortalSection
      title="Administrative audit ledger"
      subtitle={`${audit.data?.total ?? 0} immutable evidence records.`}
    >
      {audit.loading ? <PortalLoading label="Loading audit evidence" /> : null}
      {audit.error ? <PortalError error={audit.error} onRetry={audit.retry} /> : null}
      {audit.data ? <AuditTable events={audit.data.items} /> : null}
    </PortalSection>
  );
}
