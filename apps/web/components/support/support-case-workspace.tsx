"use client";

import Link from "next/link";
import { useCallback } from "react";
import { Card, EmptyState, ErrorState, LoadingState } from "@breero/ui";
import type { PortalContext } from "@breero/types";
import { useApiResource } from "@/lib/customer/use-api-resource";
import { loadPortalContext } from "@/lib/portal";
import { resolveStaffTenantScope, resolveSupportViewer, type StaffTenantScope } from "@/lib/support/case-model";
import { SUPPORT_CASE_API_STATE } from "@/lib/support/case-contract";
import styles from "./support-case.module.css";

const TENANT_SCOPE_LABELS: Record<StaffTenantScope, string> = {
  global: "All brands and providers",
  brand: "This brand",
  vendor: "Assigned provider organizations only",
  none: "No support tenant assigned",
};

/**
 * Support / trust & safety case workspace. It verifies staff access from the
 * portal context and then reports the SupportCase API's real provisioning state;
 * it never lists, creates or invents cases while that API does not exist.
 */
export function SupportCaseWorkspace() {
  const load = useCallback((signal: AbortSignal): Promise<PortalContext> => loadPortalContext(signal), []);
  const { value: context, error, retry } = useApiResource(load);

  if (error) {
    return (
      <div className="shell market-section">
        <ErrorState title="We couldn’t confirm your support access" description={error.message} onRetry={retry} />
      </div>
    );
  }
  if (!context) {
    return (
      <div className="shell market-section">
        <LoadingState label="Checking your support case access" />
      </div>
    );
  }

  const viewer = resolveSupportViewer(context);
  const tenantScope = resolveStaffTenantScope(context);
  if (viewer.kind !== "staff" || tenantScope === "none") {
    return (
      <div className="shell market-section">
        <EmptyState
          title="Support cases are restricted"
          description="Only support and trust & safety staff with case access can open this workspace."
          action={<Link className="br-button br-button--outline br-button--md" href={context.dashboard_path}>Go to your dashboard</Link>}
        />
      </div>
    );
  }

  return (
    <div className="marketplace-page">
      <section className="shell market-section">
        <p className="market-eyebrow">Support / trust &amp; safety</p>
        <h1>Support cases</h1>
        <p>Customer and provider cases, internal notes, evidence and escalations.</p>

        <Card>
          <h2>Your case access</h2>
          <dl className={styles.accessList}>
            <dt>Customer and provider messages</dt>
            <dd>Visible</dd>
            <dt>Internal notes</dt>
            <dd>{viewer.canReadInternal ? "Visible — never shared with customers or providers" : "Hidden"}</dd>
            <dt>Tenant scope</dt>
            <dd>{TENANT_SCOPE_LABELS[tenantScope]}</dd>
          </dl>
        </Card>

        {SUPPORT_CASE_API_STATE === "unprovisioned" && (
          <div role="status">
            <EmptyState
              title="The support case service isn’t available yet"
              description="BREERO has not enabled case records yet, so there are no cases to show. Nothing here is sample data. Use the support dashboard for current customer requests."
              action={<Link className="br-button br-button--outline br-button--md" href="/support">Back to support dashboard</Link>}
            />
          </div>
        )}
      </section>
    </div>
  );
}
