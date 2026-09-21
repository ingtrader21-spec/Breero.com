import { PortalApp, type PortalConfig } from "@breero/portal";
const config: PortalConfig = { name: "Operations Portal", eyebrow: "Service operations", allowedRoles: ["operations", "admin"], sections: [
  { label: "Dispatch", path: "/admin/bookings", description: "Awaiting assignment, reassignment, and upcoming work queues." },
  { label: "Bookings", path: "/admin/bookings", description: "Authorized booking operations and service-local windows." },
  { label: "Providers", path: "/admin/providers", description: "Provider records available to operations for matching and approval workflows." },
  { label: "Provider applications", path: "/admin/provider-applications", description: "Pending and under-review provider onboarding applications." },
  { label: "Audit log", path: "/admin/audit-events", description: "Immutable dispatch and administration history." },
  { label: "Integration failures", path: "/integrations/failures", description: "Durable delivery failures that may require an authorized retry." },
  { label: "Integration health", path: "/integrations/health", description: "Configured integration and outbox delivery health." },
  { label: "System health", path: "/integrations/health", description: "Database-backed integration and outbox delivery health." }
] };
export default function Page() { return <PortalApp config={config} />; }
