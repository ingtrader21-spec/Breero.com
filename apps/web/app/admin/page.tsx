import { PortalHome } from "@/components/portal/portal-home";

export const metadata = { title: "Administration dashboard" };

export default function AdminDashboard() {
  return <PortalHome title="Administration dashboard" emailHref="/admin/email"/>;
}
