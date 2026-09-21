import { PortalApp, type PortalConfig } from "@breero/portal";
const config: PortalConfig = { name: "Partner Portal", eyebrow: "Provider workspace", allowedRoles: ["vendor_admin"], sections: [
  { label: "Overview", path: "/provider/profile", description: "Provider onboarding, compliance, and account status." },
  { label: "Jobs", path: "/provider/jobs", description: "Only jobs assigned to this provider organization or professional." },
  { label: "Calendar", path: "/provider/jobs", description: "Assigned work in service-address time order." },
  { label: "Availability", path: "/provider/availability", description: "Working hours and Sunday emergency restrictions." },
  { label: "Service areas", path: "/provider/service-areas", description: "Provider-owned coverage requests and approval state." },
  { label: "Services", path: "/provider/services", description: "BREERO catalog services selected by this provider." },
  { label: "Capacity", path: "/provider/capacity", description: "Daily job and work-minute limits." },
  { label: "Business profile", path: "/provider/profile", description: "Provider organization profile and onboarding status." }
] };
export default function Page() { return <PortalApp config={config} />; }
