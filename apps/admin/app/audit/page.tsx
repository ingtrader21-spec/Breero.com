import type { Metadata } from "next";

import { AuditConsole } from "../../features/audit/AuditConsole";
import "../../features/audit/audit.css";

export const metadata: Metadata = { title: "Audit log · BREERO Admin", robots: { index: false, follow: false } };

export default function AuditPage() {
  return <AuditConsole />;
}
