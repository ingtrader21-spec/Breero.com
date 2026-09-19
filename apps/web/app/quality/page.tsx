import { DepartmentDashboard } from "@/components/portal/department-dashboard";

export const metadata = { title: "Quality dashboard" };

const modules = [
  { title: "Jobs", description: "Completed and in-progress work available for quality review.", permission: "quality.jobs.read" },
  { title: "Reviews", description: "Quality review records and follow-up.", permission: "quality.reviews.read" },
  { title: "Providers", description: "Provider quality records.", permission: "quality.providers.read" },
];

export default function QualityDashboard() {
  return <DepartmentDashboard department="quality" eyebrow="Quality assurance" title="Quality dashboard" description="Your authorized service-quality workspace." modules={modules}/>;
}
