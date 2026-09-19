import { DepartmentDashboard } from "@/components/portal/department-dashboard";

export const metadata = { title: "Operations dashboard" };

const modules = [
  { title: "Dispatch queue", description: "Service requests awaiting operational handling.", permission: "ops.dispatch.read" },
  { title: "Bookings", description: "Operational booking visibility and controls.", permission: "ops.bookings.read" },
  { title: "Providers", description: "Provider operational records.", permission: "ops.providers.read" },
  { title: "Customers", description: "Customer records needed for service operations.", permission: "ops.customers.read" },
  { title: "Audit", description: "Operational audit visibility for authorized managers.", permission: "ops.audit.read" },
];

export default function OperationsDashboard() {
  return <DepartmentDashboard department="dispatch" eyebrow="Operations" title="Dispatch dashboard" description="Your authorized booking and dispatch workspace." modules={modules}/>;
}
