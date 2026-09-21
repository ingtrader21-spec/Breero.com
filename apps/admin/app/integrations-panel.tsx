"use client";

import { useState } from "react";

import {
  DataTable,
  formatDate,
  formatLabel,
  PortalConfirmForm,
  PortalError,
  PortalLoading,
  PortalNotice,
  PortalSection,
  StatusBadge,
  type DataColumn,
  usePortalQuery,
  usePortalSession,
} from "@breero/portal";

import type { Capabilities, IntegrationConfig, IntegrationOperation } from "./admin-types";

export function IntegrationsPanel({
  capabilities,
  onChanged,
}: {
  capabilities: Capabilities | null;
  onChanged: () => void;
}) {
  const config = usePortalQuery<IntegrationConfig>("/integrations/config");
  const operations = usePortalQuery<IntegrationOperation[]>("/integrations/operations");
  const { request } = usePortalSession();
  const [message, setMessage] = useState("");
  const activateReady = Boolean(
    capabilities?.middleware_delivery &&
      config.data?.middleware_enabled &&
      config.data.middleware_url_configured &&
      config.data.middleware_ca_configured &&
      config.data.middleware_client_certificate_configured &&
      config.data.middleware_hmac_configured &&
      config.data.middleware_identity_configured,
  );

  async function operate(kind: "activate-pending" | "park-unconfigured") {
    const result = await request<IntegrationOperation>(`/integrations/outbox/${kind}`, {
      method: "POST",
    });
    setMessage(`${formatLabel(result.operation_type)} affected ${result.affected_count} events.`);
    operations.retry();
    onChanged();
  }

  const columns: DataColumn<IntegrationOperation>[] = [
    {
      key: "time",
      label: "Time",
      render: (item) => formatDate(item.created_at),
    },
    {
      key: "operation",
      label: "Operation",
      render: (item) => <strong>{formatLabel(item.operation_type)}</strong>,
    },
    {
      key: "actor",
      label: "Actor",
      render: (item) => <span className="portal-code">{item.actor_id ?? "system"}</span>,
    },
    {
      key: "affected",
      label: "Affected",
      compact: true,
      render: (item) => item.affected_count,
    },
    {
      key: "before",
      label: "Before",
      render: (item) => JSON.stringify(item.before_counts),
    },
    {
      key: "after",
      label: "After",
      render: (item) => JSON.stringify(item.after_counts),
    },
  ];

  return (
    <div className="portal-stack">
      {message ? (
        <PortalNotice title="Integration operation completed" tone="success">
          {message}
        </PortalNotice>
      ) : null}
      <div className="portal-split">
        <PortalSection
          title="Configuration state"
          subtitle="Only configured/not-configured signals are exposed; secrets are never returned."
        >
          {config.loading ? <PortalLoading label="Loading integration configuration" /> : null}
          {config.error ? <PortalError error={config.error} onRetry={config.retry} /> : null}
          {config.data ? (
            <dl className="portal-definition-grid">
              {Object.entries(config.data).map(([key, value]) => (
                <div key={key}>
                  <dt>{formatLabel(key)}</dt>
                  <dd>
                    <StatusBadge value={value ? "enabled" : "disabled"} />
                  </dd>
                </div>
              ))}
            </dl>
          ) : null}
        </PortalSection>
        <PortalSection
          title="Durable outbox operations"
          subtitle="State changes are explicit, confirmed, authenticated, and evidence-backed."
        >
          <PortalConfirmForm
            title="Activate pending configuration events"
            description="Moves eligible PENDING_CONFIGURATION events back into delivery only when middleware delivery and every required private configuration signal are active."
            confirmLabel="Activate pending events"
            disabled={!activateReady}
            onConfirm={() => operate("activate-pending")}
          />
          {!activateReady ? (
            <PortalNotice title="Activation remains blocked" tone="warning">
              Middleware delivery or a required private configuration value is not active. The
              interface cannot override that fail-closed state.
            </PortalNotice>
          ) : null}
          <PortalConfirmForm
            title="Park unconfigured events"
            description="Moves currently pending or retryable integration events to PENDING_CONFIGURATION so external delivery cannot continue without valid configuration."
            confirmLabel="Park unconfigured events"
            onConfirm={() => operate("park-unconfigured")}
          />
        </PortalSection>
      </div>
      <PortalSection
        title="Integration operation history"
        subtitle="Before/after counts prove each administrative outbox change."
      >
        {operations.loading ? <PortalLoading label="Loading integration operations" /> : null}
        {operations.error ? <PortalError error={operations.error} onRetry={operations.retry} /> : null}
        {operations.data ? (
          <DataTable
            rows={operations.data}
            columns={columns}
            rowKey={(item) => item.id}
            emptyTitle="No integration operations are recorded"
          />
        ) : null}
      </PortalSection>
    </div>
  );
}
