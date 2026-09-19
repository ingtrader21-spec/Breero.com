import { DepartmentDashboard } from "@/components/portal/department-dashboard";

export const metadata = { title: "Trust and safety dashboard" };

const modules = [
  { title: "Providers", description: "Provider trust and safety records.", permission: "trust.providers.read" },
  { title: "Credentials", description: "Credential verification controls.", permission: "trust.credentials.manage" },
  { title: "Reviews", description: "Trust-related review and escalation records.", permission: "trust.reviews.manage" },
  { title: "Audit", description: "Security and trust audit history.", permission: "trust.audit.read" },
];

export default function TrustSafetyDashboard() {
  return <DepartmentDashboard department="trust_safety" eyebrow="Trust & safety" title="Trust & safety dashboard" description="Your authorized provider trust, credential, and audit workspace." modules={modules}/>;
}
