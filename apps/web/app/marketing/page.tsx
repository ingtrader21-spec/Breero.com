import { DepartmentDashboard } from "@/components/portal/department-dashboard";

export const metadata = { title: "Marketing dashboard" };

const modules = [
  { title: "Campaigns", description: "Campaign records available to marketing.", permission: "marketing.campaigns.read" },
  { title: "Consent", description: "Communication consent evidence.", permission: "marketing.consents.read" },
  { title: "Suppressions", description: "Communication suppression records.", permission: "marketing.suppressions.read" },
];

export default function MarketingDashboard() {
  return <DepartmentDashboard department="marketing" eyebrow="Marketing" title="Marketing dashboard" description="Your authorized campaign, consent, and suppression workspace." modules={modules}/>;
}
