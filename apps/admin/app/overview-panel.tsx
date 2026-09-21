"use client";

import {
  CapabilityGrid,
  formatMoney,
  MetricCard,
  PortalEmpty,
  PortalError,
  PortalLoading,
  PortalSection,
  StatusBadge,
  usePortalQuery,
} from "@breero/portal";

import { AuditTable } from "./audit-panel";
import type { AdminOverview, StatusCount } from "./admin-types";
import { total } from "./admin-types";

export function OverviewPanel({
  query,
}: {
  query: ReturnType<typeof usePortalQuery<AdminOverview>>;
}) {
  if (query.loading) return <PortalLoading label="Loading administration overview" />;
  if (query.error) return <PortalError error={query.error} onRetry={query.retry} />;
  const data = query.data;
  if (!data) return <PortalEmpty title="Administrative overview is unavailable" />;
  const available = data.earnings
    .filter((item) => item.status === "AVAILABLE")
    .reduce((sum, item) => sum + item.amount_minor, 0);
  const currency = data.earnings[0]?.currency ?? "USD";
  const outboxAttention = total(data.outbox, [
    "FAILED_RETRYABLE",
    "FAILED_TERMINAL",
    "RETRYING",
    "PENDING_CONFIGURATION",
  ]);
  return (
    <>
      <section className="portal-metric-grid" aria-label="Administration summary">
        <MetricCard
          label="Active users"
          value={`${data.users_active}/${data.users_total}`}
          detail={`${data.customers_total} customer profiles`}
          tone="success"
        />
        <MetricCard
          label="Service zones"
          value={`${data.service_zones_active}/${data.service_zones_total}`}
          detail={`${data.postal_codes_active}/${data.postal_codes_total} postal codes active`}
        />
        <MetricCard
          label="Available earnings"
          value={formatMoney(available, currency)}
          detail="Eligible before payout batching"
        />
        <MetricCard
          label="Delivery attention"
          value={outboxAttention}
          detail="Durable integration states"
          tone={outboxAttention ? "danger" : "success"}
        />
      </section>
      <div className="portal-split">
        <PortalSection
          title="Marketplace workload"
          subtitle="Current status counts across core records."
        >
          <div className="portal-stack">
            <StatusLine title="Bookings" rows={data.bookings} />
            <StatusLine title="Jobs" rows={data.jobs} />
            <StatusLine title="Providers" rows={data.vendors} />
            <StatusLine title="Applications" rows={data.provider_applications} />
            <StatusLine title="Payout batches" rows={data.payout_batches} />
          </div>
        </PortalSection>
        <PortalSection
          title="Recent audit evidence"
          subtitle="Newest high-level platform changes."
        >
          <AuditTable events={data.recent_audit.slice(0, 12)} />
        </PortalSection>
      </div>
      <PortalSection
        title="Effective capabilities"
        subtitle="Administrative interfaces show runtime state but do not bypass disabled controls."
      >
        <CapabilityGrid capabilities={data.capabilities} />
      </PortalSection>
    </>
  );
}

function StatusLine({ title, rows }: { title: string; rows: StatusCount[] }) {
  return (
    <div>
      <strong>{title}</strong>
      <div className="portal-inline">
        {rows.length ? (
          rows.map((row) => (
            <span className="portal-inline" key={`${title}-${row.status}`}>
              <StatusBadge value={row.status} />
              <strong>{row.count}</strong>
            </span>
          ))
        ) : (
          <span className="portal-muted">No records</span>
        )}
      </div>
    </div>
  );
}
