"use client";

import Link from "next/link";
import { PageHeader } from "../components/AdminShell";
import { NAVIGATION } from "../lib/navigation";
import { Notice, Section } from "../components/ui";

const DESCRIPTIONS: Record<string, string> = {
  "/users": "Search accounts, review effective access, edit role assignments, and disable or reactivate Breero access.",
  "/providers": "Review submitted provider applications and approve, reject or request more information.",
  "/geography": "Manage service zones, their coverage selectors and deactivation.",
  "/geography/postal-codes": "Maintain postal-code coverage one row at a time or through validated CSV import.",
  "/finance": "Earnings totals, pending payout amounts and finance exceptions from persisted records.",
  "/finance/payouts": "Create, review, approve and submit payout batches behind the existing payout gate.",
  "/finance/payments": "Read-only payment and refund inventory. Refund and capture commands are not exposed here.",
};

export default function OverviewPage() {
  return (
    <>
      <PageHeader eyebrow="Governance workspace" title="Admin & Finance" />
      <Notice title="Identity authority">
        Keycloak remains the identity authority. This workspace manages Breero-owned access state only: role assignments and whether an account may use Breero portals.
      </Notice>
      <Section title="Workspaces">
        <div className="admin-grid">
          {NAVIGATION.filter((item) => item.href !== "/").map((item) => (
            <article key={item.href} className="admin-card">
              <h3><Link href={item.href}>{item.label}</Link></h3>
              <p>{DESCRIPTIONS[item.href]}</p>
            </article>
          ))}
        </div>
      </Section>
    </>
  );
}
