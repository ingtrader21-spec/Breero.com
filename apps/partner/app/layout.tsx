import type { Metadata } from "next";
import "@breero/portal/styles.css";
import "./partner.css";
export const metadata: Metadata = { title: "BREERO Partner", description: "Secure BREERO provider workspace", robots: { index: false, follow: false } };
export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body>{children}</body></html>; }
