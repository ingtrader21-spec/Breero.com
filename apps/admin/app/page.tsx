import { PortalApp, type PortalConfig } from "@breero/portal";
const config: PortalConfig = { name: "Admin & Finance", eyebrow: "Governance workspace", allowedRoles: ["finance", "admin"], sections: [
  { label: "Service catalog", path: "/services", description: "The live service catalog and pricing modes exposed by the canonical API." },
  { label: "Bookings", path: "/admin/bookings", description: "Booking and request administration." },
  { label: "Providers", path: "/admin/providers", description: "Provider approval records available to authorized administrators." },
  { label: "Provider applications", path: "/admin/provider-applications", description: "Provider onboarding approval queue." },
  { label: "Operating hours", path: "/admin/operating-hours", description: "Service-address-local operating hours." },
  { label: "Feature flags", path: "/admin/feature-flags", description: "Protected production side-effect controls." },
  { label: "Audit log", path: "/admin/audit-events", description: "Immutable administration and dispatch history." },
  { label: "Earnings", path: "/finance/earnings", description: "Authoritative provider earnings. This view never calculates or invents financial values." },
  { label: "Integration health", path: "/integrations/health", description: "Current backend integration configuration and delivery health." },
  { label: "Integration failures", path: "/integrations/failures", description: "Durable failures available for authorized investigation and retry." },
  { label: "Payments & refunds", description: "Finance-wide payment and refund listing is not yet exposed by a canonical API." },
  { label: "Lead disputes", description: "Finance-wide dispute review and resolution is not yet exposed by a canonical API." },
  { label: "Payout batches", description: "Payout commands exist, but a list/read projection is not yet exposed." },
  { label: "Users & roles", description: "Internal accounts are created only through the protected administrator operation." }
] };
export default function Page() { return <PortalApp config={config} />; }
