import type { Metadata } from "next";
import Link from "next/link";
import { ShieldIcon } from "@breero/ui";

export const metadata: Metadata = {
  title: "Access required",
  description: "Your BREERO account does not currently have an active workspace assignment.",
};

export default function AccessDeniedPage() {
  return (
    <main className="marketplace-page">
      <section className="shell market-section" aria-labelledby="access-denied-title">
        <p className="market-eyebrow">Workspace access</p>
        <h1 id="access-denied-title">Your account does not have an active workspace</h1>
        <div className="hero-panel">
          <p>
            <ShieldIcon size={18} /> BREERO denied this workspace request because your current
            effective access profile does not authorize a department dashboard.
          </p>
          <p>
            Sign-in succeeded, but no protected records or actions were exposed. Ask an authorized
            administrator to review your brand, department, role, and tenant-scope assignments.
          </p>
          <div className="button-row">
            <Link className="br-button br-button--primary br-button--md" href="/contact">
              Contact support
            </Link>
            <Link className="br-button br-button--secondary br-button--md" href="/">
              Return home
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
