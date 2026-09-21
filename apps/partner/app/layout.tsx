import type { Metadata } from "next";
import "@breero/portal/styles.css";

export const metadata: Metadata = {
  title: { default: "BREERO Partner", template: "%s | BREERO Partner" },
  description: "Secure provider operations, workforce, jobs, compliance, earnings, and payout visibility.",
  robots: { index: false, follow: false, nocache: true },
};

export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
