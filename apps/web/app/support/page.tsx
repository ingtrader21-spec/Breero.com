import { DepartmentDashboard } from "@/components/portal/department-dashboard";

export const metadata = { title: "Customer support dashboard" };

const modules = [
  { title: "Customers", description: "Customer records available to support.", permission: "support.customers.read" },
  { title: "Service requests", description: "Customer service requests and follow-up.", permission: "support.requests.read" },
  { title: "Bookings", description: "Booking details needed for customer support.", permission: "support.bookings.read" },
  { title: "Communications", description: "Authorized customer communication history.", permission: "support.communications.read" },
];

export default function SupportDashboard() {
  return <DepartmentDashboard department="customer_support" eyebrow="Customer support" title="Support dashboard" description="Your authorized customer-service workspace." modules={modules}/>;
}
