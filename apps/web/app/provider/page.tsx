import { PortalHome } from "@/components/portal/portal-home";

export const metadata = { title: "Provider dashboard" };

export default function ProviderDashboard() {
  return <PortalHome title="Provider dashboard" emailHref="/provider/email"/>;
}
