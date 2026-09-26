import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ConfirmAction } from "../components/ConfirmAction";
import { EffectiveAccessView } from "../components/EffectiveAccessView";
import { FinanceStatusNotice } from "../components/FinanceStatusNotice";
import { PayoutTimeline } from "../components/PayoutTimeline";
import { Pager, StatusBadge } from "../components/ui";
import type { EffectiveAccess } from "../lib/types";

describe("StatusBadge and Pager", () => {
  it("renders tone classes and humanized labels", () => {
    const html = renderToStaticMarkup(<StatusBadge value="PENDING_APPROVAL" tone="warning" />);
    expect(html).toContain("admin-badge--warning");
    expect(html).toContain("Pending approval");
  });

  it("disables out-of-range pages", () => {
    const html = renderToStaticMarkup(<Pager page={1} pageSize={25} total={10} onPage={() => undefined} />);
    expect(html).toContain("Page 1 of 1 · 10 total");
    expect(html.match(/disabled=""/g)).toHaveLength(2);
  });
});

describe("FinanceStatusNotice", () => {
  it("states disabled and not-implemented capabilities explicitly", () => {
    const html = renderToStaticMarkup(
      <FinanceStatusNotice status={{ payouts_enabled: false, payments_enabled: false, capabilities: { payout_commands: "DISABLED", refund_commands: "NOT_IMPLEMENTED", payout_transfer: "NOT_IMPLEMENTED" } }} />,
    );
    expect(html).toContain("Payout commands disabled");
    expect(html).toContain("Refund commands");
    expect(html).toContain("Payout transfer");
    expect(html).toContain("fail closed");
  });

  it("is silent about payouts when they are enabled", () => {
    const html = renderToStaticMarkup(<FinanceStatusNotice status={{ payouts_enabled: true, payments_enabled: true, capabilities: {} }} />);
    expect(html).toBe("");
  });
});

describe("PayoutTimeline", () => {
  it("reads back the batch lifecycle", () => {
    const html = renderToStaticMarkup(
      <PayoutTimeline history={[
        { state: "CREATED", status: "PENDING_APPROVAL", occurred_at: "2026-09-01T10:00:00Z", actor_id: "aaaaaaaa-1111" },
        { state: "APPROVED", status: "APPROVED", occurred_at: "2026-09-01T11:00:00Z", actor_id: "bbbbbbbb-2222" },
        { state: "SUBMISSION_BLOCKED", status: "APPROVED", occurred_at: null, detail: "integration_not_configured" },
        { state: "CURRENT", status: "APPROVED", occurred_at: null },
      ]} />,
    );
    expect(html).toContain("Created for review");
    expect(html).toContain("by aaaaaaaa");
    expect(html).toContain("Submission blocked");
    expect(html).toContain("integration_not_configured");
    expect(html).toContain("Current state</strong>: Approved");
  });
});

describe("ConfirmAction", () => {
  it("renders only the trigger until opened, so nothing is sent without confirmation", () => {
    const html = renderToStaticMarkup(
      <ConfirmAction label="Disable Breero access" title="t" description="d" tone="danger" onConfirm={async () => undefined} />,
    );
    expect(html).toContain("Disable Breero access");
    expect(html).toContain("admin-button--danger");
    expect(html).not.toContain("alertdialog");
  });

  it("can be disabled", () => {
    const html = renderToStaticMarkup(<ConfirmAction label="Save" title="t" description="d" disabled onConfirm={async () => undefined} />);
    expect(html).toContain("disabled");
  });
});

describe("EffectiveAccessView", () => {
  const access: EffectiveAccess = {
    user_id: "u1",
    brand_key: "breero",
    status: "disabled",
    identity_authority: "keycloak",
    managed_profile: false,
    access: {
      user: { id: "u1", email: "a@b.co", full_name: "A", role: "finance", is_active: false, email_verified: true },
      brand_key: "breero",
      dashboard_path: "/finance",
      roles: ["finance"],
      departments: ["finance"],
      permissions: ["finance.payouts.read"],
      assignments: [],
      identity_mode: "keycloak",
    },
    overrides: [{ permission: "finance.refunds.read", allow: false, source: "user", role: null }],
    effective_permissions: [],
  };

  it("shows suspension, default access and overrides", () => {
    const html = renderToStaticMarkup(<EffectiveAccessView access={access} />);
    expect(html).toContain("Access suspended");
    expect(html).toContain("Default access");
    expect(html).toContain("Effective permissions (0)");
    expect(html).toContain("No effective permissions.");
    expect(html).toContain("finance.refunds.read");
    expect(html).toContain("Deny");
  });
});
