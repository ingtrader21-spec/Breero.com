import type { Metadata } from "next";
import "@breero/portal/styles.css";
import "./ops.css";
import { Shell } from "../components/Shell";

export const metadata: Metadata = { title: "BREERO Operations", description: "Secure BREERO operations control center", robots: { index: false, follow: false } };

export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><Shell>{children}</Shell></body></html>;
}
