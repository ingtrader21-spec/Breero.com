import { DepartmentDashboard } from "@/components/portal/department-dashboard";

export const metadata = { title: "Sales dashboard" };

const modules = [
  { title: "Leads", description: "Authorized lead and opportunity records.", permission: "sales.leads.read" },
  { title: "Providers", description: "Provider records available to sales.", permission: "sales.providers.read" },
];

export default function SalesDashboard() {
  return <DepartmentDashboard department="sales" eyebrow="Sales" title="Sales dashboard" description="Your authorized provider and opportunity workspace." modules={modules}/>;
}
