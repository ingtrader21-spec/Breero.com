import type { Metadata } from "next";
import "@breero/portal/styles.css";
import "./admin.css";
import { AdminShell } from "../components/AdminShell";

export const metadata: Metadata = { title: "BREERO Admin", description: "Secure BREERO administration and finance workspace", robots: { index: false, follow: false } };
export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><AdminShell>{children}</AdminShell></body></html>;
}
