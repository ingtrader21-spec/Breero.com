import type { Metadata } from "next";
import "@breero/portal/styles.css";

export const metadata: Metadata = {
  title: { default: "BREERO Administration", template: "%s | BREERO Administration" },
  description: "Secure BREERO governance, finance, payout, service-zone, access, and audit control plane.",
  robots: { index: false, follow: false, nocache: true },
};

export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
