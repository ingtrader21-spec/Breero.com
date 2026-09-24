import { AccessAssignmentForm } from "@/components/portal/access-assignment-form";
import { DepartmentDashboard } from "@/components/portal/department-dashboard";

export const metadata = { title: "Administration dashboard" };

const modules = [
  {
    title: "Access control",
    description: "Department and role access administration.",
    permission: "admin.access.manage",
    href: "#access-assignment",
  },
  { title: "Audit", description: "Administrative audit records.", permission: "admin.audit.read" },
  { title: "Capabilities", description: "Runtime capability state and release controls.", permission: "admin.capabilities.read" },
  { title: "Integrations", description: "Integration health and configuration visibility.", permission: "admin.integrations.read" },
  { title: "Marketplace analytics", description: "Scoped marketplace metrics with projection freshness.", permission: "analytics.marketplace.read", href: "/ops/analytics" },
];

export default function AdminDashboard() {
  return (
    <>
      <DepartmentDashboard
        department="administration"
        eyebrow="Administration"
        title="Administration dashboard"
        description="Your authorized access, audit, capability, and integration workspace."
        modules={modules}
      />
      <section className="shell market-section">
        <AccessAssignmentForm />
      </section>
    </>
  );
}
