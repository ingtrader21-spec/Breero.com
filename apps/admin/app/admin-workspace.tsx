"use client";

import { useState } from "react";

import {
  PortalApplication,
  PortalSessionProvider,
  type PortalNavigationItem,
  usePortalQuery,
  usePortalSession,
} from "@breero/portal";

import { portalRuntime } from "../portal.config";
import { AuditPanel } from "./audit-panel";
import type { AdminOverview } from "./admin-types";
import { total } from "./admin-types";
import { FinancePanel } from "./finance-panel";
import { GeographyPanel } from "./geography-panel";
import { IntegrationsPanel } from "./integrations-panel";
import { OverviewPanel } from "./overview-panel";
import { SecurityPanel } from "./security-panel";
import { UsersPanel } from "./users-panel";

function AdminWorkspace() {
  const { state } = usePortalSession();
  const permissions = state.status === "authenticated" ? state.session.context.permissions : [];
  const admin = permissions.includes("*") || permissions.some((item) => item.startsWith("admin."));
  const finance =
    admin || permissions.includes("*") || permissions.some((item) => item.startsWith("finance."));
  const [activeId, setActiveId] = useState(admin ? "overview" : "finance");
  const overview = usePortalQuery<AdminOverview>(admin ? "/portal/admin/overview" : null);
  const auditAttention = overview.data
    ? total(overview.data.outbox, ["FAILED_RETRYABLE", "FAILED_TERMINAL", "RETRYING"])
    : 0;
  const navigation: PortalNavigationItem[] = [
    ...(admin
      ? [
          {
            id: "overview",
            label: "Overview",
            description: "Platform health, governance workload, and capability state.",
          },
        ]
      : []),
    ...(admin
      ? [
          {
            id: "users",
            label: "Users & access",
            description: "Identity shadows, role assignments, departments, and tenant scope.",
            badge: overview.data?.users_total,
          },
        ]
      : []),
    ...(admin
      ? [
          {
            id: "geography",
            label: "Service zones",
            description: "Service boundaries, postal coverage, timezone, and activation state.",
            badge: overview.data?.service_zones_active,
          },
        ]
      : []),
    ...(finance
      ? [
          {
            id: "finance",
            label: "Finance & payouts",
            description:
              "Compensation plans, immutable earnings, review, approval, and submission.",
          },
        ]
      : []),
    ...(admin
      ? [
          {
            id: "integrations",
            label: "Integrations",
            description:
              "Middleware/Odoo configuration state and durable outbox operations.",
            badge: auditAttention || undefined,
          },
        ]
      : []),
    ...(admin
      ? [
          {
            id: "audit",
            label: "Audit",
            description: "Recent immutable administrative and financial evidence.",
          },
        ]
      : []),
    {
      id: "security",
      label: "Security",
      description: "Effective authority, session boundary, and separation of duties.",
    },
  ];
  const active = navigation.some((item) => item.id === activeId)
    ? activeId
    : (navigation[0]?.id ?? "security");
  return (
    <PortalApplication
      config={portalRuntime}
      navigation={navigation}
      activeId={active}
      onNavigate={setActiveId}
    >
      {active === "overview" ? <OverviewPanel query={overview} /> : null}
      {active === "users" ? <UsersPanel /> : null}
      {active === "geography" ? <GeographyPanel onChanged={overview.retry} /> : null}
      {active === "finance" ? (
        <FinancePanel
          capabilities={state.status === "authenticated" ? state.session.capabilities : null}
          onChanged={overview.retry}
        />
      ) : null}
      {active === "integrations" ? (
        <IntegrationsPanel
          capabilities={state.status === "authenticated" ? state.session.capabilities : null}
          onChanged={overview.retry}
        />
      ) : null}
      {active === "audit" ? <AuditPanel /> : null}
      {active === "security" ? <SecurityPanel /> : null}
    </PortalApplication>
  );
}

export default function AdminPortal() {
  return (
    <PortalSessionProvider>
      <AdminWorkspace />
    </PortalSessionProvider>
  );
}
