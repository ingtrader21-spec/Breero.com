import { DepartmentDashboard } from "@/components/portal/department-dashboard";

export const metadata = { title: "Provider dashboard" };

const modules = [
  { title: "Company profile", description: "Provider identity and service coverage.", permission: "provider.profile.read" },
  { title: "Credentials", description: "License and insurance verification records.", permission: "provider.credentials.read" },
  { title: "Team", description: "Provider team access.", permission: "provider.worker.manage" },
  { title: "Availability", description: "Service availability.", permission: "provider.availability.manage" },
  { title: "Jobs", description: "Assigned service work.", permission: "provider.jobs.read" },
  { title: "Quotes", description: "Service quotes.", permission: "provider.quotes.manage" },
];

export default function ProviderDashboard() {
  return <DepartmentDashboard department={["provider", "vendor_success"]} eyebrow="Provider operations" title="Provider dashboard" description="Your authorized provider and vendor-success workspace." modules={modules}/>;
}
