import { DepartmentDashboard } from "@/components/portal/department-dashboard";

export const metadata = { title: "Field service dashboard" };

const modules = [
  { title: "My profile", description: "Field-service profile and account details.", permission: "worker.profile.read" },
  { title: "Schedule", description: "Assigned service schedule.", permission: "worker.schedule.read" },
  { title: "Availability", description: "Field-service availability.", permission: "worker.availability.manage" },
  { title: "Jobs", description: "Assigned jobs and permitted status updates.", permission: "worker.jobs.read" },
];

export default function WorkerDashboard() {
  return <DepartmentDashboard department="field_service" eyebrow="Field service" title="Worker dashboard" description="Your authorized field-service workspace." modules={modules}/>;
}
