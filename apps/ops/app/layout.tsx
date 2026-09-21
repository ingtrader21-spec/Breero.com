import type { Metadata } from "next";
import "@breero/portal/styles.css";

export const metadata: Metadata = {
  title: { default: "BREERO Operations", template: "%s | BREERO Operations" },
  description: "Secure dispatch, matching, provider, booking, and service-delivery operations.",
  robots: { index: false, follow: false, nocache: true },
};

export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
