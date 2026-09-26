import { describe, expect, it } from "vitest";
import { describeAccessChange, grantsPrivilege, newAssignment, setScope, validateAssignments, validateReason } from "../lib/access";
import { formatDateTime, formatMinor, humanize } from "../lib/format";
import { buildZoneCreatePayload, describeCoverage, normalizePostalCode, parsePostalCodeCsv, parsePostalCodeList } from "../lib/geography";
import { isActivePath } from "../lib/navigation";
import { payoutViewState } from "../lib/payouts";
import { allowedDecisions, sectionRows, validateDecisionReason } from "../lib/providers";
import { canUseAdminPortal, parseSession } from "../lib/session";
import type { FinanceStatus, PayoutBatchDetail } from "../lib/types";

const VENDOR = "0f8fad5b-d9cb-469f-a165-70867728950e";

describe("access editor rules", () => {
  it("mirrors API validation for primary, duplicates and vendor scope", () => {
    const support = newAssignment("support", true);
    expect(validateAssignments([support])).toEqual([]);
    expect(validateAssignments([support, { ...support }])).toEqual([
      "Only one assignment can be primary.",
      "Assignment 2 duplicates support in customer_support.",
    ]);
    const vendorScoped = setScope(newAssignment("vendor_admin"), "vendor", null);
    expect(validateAssignments([vendorScoped])).toEqual(["Assignment 1 needs a valid vendor ID for vendor scope."]);
    expect(validateAssignments([setScope(newAssignment("vendor_admin"), "vendor", VENDOR)])).toEqual([]);
    expect(validateAssignments([{ ...newAssignment("finance"), vendor_id: VENDOR }])).toEqual([
      "Assignment 1 can only carry a vendor ID in vendor scope.",
    ]);
  });

  it("clears the vendor when leaving vendor scope", () => {
    const scoped = setScope(newAssignment("vendor_admin"), "vendor", VENDOR);
    expect(setScope(scoped, "brand", VENDOR).vendor_id).toBeNull();
  });

  it("flags privileged grants and summarizes changes", () => {
    expect(grantsPrivilege([newAssignment("admin")])).toBe(true);
    expect(grantsPrivilege([newAssignment("finance")])).toBe(false);
    expect(newAssignment("admin").tenant_scope).toBe("global");
    expect(describeAccessChange([newAssignment("support")], [newAssignment("finance")])).toEqual({ added: ["finance"], removed: ["support"] });
  });

  it("requires a meaningful reason", () => {
    expect(validateReason("  ")).not.toBeNull();
    expect(validateReason("ok")).not.toBeNull();
    expect(validateReason("policy breach")).toBeNull();
    expect(validateReason("x".repeat(501))).not.toBeNull();
  });
});

describe("money and dates", () => {
  it("formats minor units exactly without float drift", () => {
    expect(formatMinor(123456, "USD")).toBe("$1,234.56");
    expect(formatMinor(-5, "USD")).toBe("-$0.05");
    expect(formatMinor(1000, "JPY")).toBe("¥1,000");
    expect(formatMinor(9007199254740991, "USD")).toBe("$90,071,992,547,409.91");
    expect(formatMinor(1.5, "USD")).toBe("—");
    expect(formatMinor(100, "NOTACURRENCY")).toBe("100 NOTACURRENCY (minor units)");
  });

  it("renders timestamps in UTC and tolerates nulls", () => {
    // Newer ICU versions separate the time and "PM" with U+202F, matched by \s.
    expect(formatDateTime("2026-09-25T12:30:00Z")).toMatch(/^Sep 25, 2026, 12:30\sPM UTC$/u);
    expect(formatDateTime(null)).toBe("—");
    expect(formatDateTime("not a date")).toBe("—");
    expect(humanize("PENDING_APPROVAL")).toBe("Pending approval");
  });
});

function batch(overrides: Partial<PayoutBatchDetail> = {}): PayoutBatchDetail {
  return {
    id: "b1", reference: "PAY-1", status: "PENDING_APPROVAL", currency: "USD", total_minor: 1000, earning_count: 1,
    reviewed_by: "u1", reviewed_at: null, approved_by: null, approved_at: null, submitted_at: null, provider_status: null,
    failure_reason: null, created_at: "2026-09-01T00:00:00Z", provider_reference: null, earnings: [], vendor_totals: [],
    history: [], allowed_actions: ["approve"], payouts_enabled: true, ...overrides,
  };
}

const ENABLED: FinanceStatus = { payouts_enabled: true, payments_enabled: false, capabilities: { payout_transfer: "NOT_IMPLEMENTED" } };

describe("payout view state", () => {
  it("offers only server-allowed actions", () => {
    expect(payoutViewState(batch(), ENABLED).actions).toEqual(["approve"]);
  });

  it("hides every action while payouts are disabled", () => {
    const state = payoutViewState(batch({ payouts_enabled: false }), { ...ENABLED, payouts_enabled: false });
    expect(state.actions).toEqual([]);
    expect(state.blockedReason).toMatch(/PAYOUT_ENABLED=false/);
    // A stale enabled read model cannot re-enable actions when status says disabled.
    expect(payoutViewState(batch(), { ...ENABLED, payouts_enabled: false }).actions).toEqual([]);
  });

  it("explains the four-eyes block", () => {
    const state = payoutViewState(batch({ allowed_actions: [] }), ENABLED);
    expect(state.blockedReason).toMatch(/different finance approver/);
  });

  it("warns that submission fails closed without a transfer adapter", () => {
    const state = payoutViewState(batch({ status: "APPROVED", allowed_actions: ["submit"] }), ENABLED);
    expect(state.actions).toEqual(["submit"]);
    expect(state.blockedReason).toMatch(/fail closed/);
  });

  it("reads back blocked and failed states", () => {
    expect(payoutViewState(batch({ status: "APPROVED", failure_reason: "integration_not_configured", allowed_actions: [] }), ENABLED).headline).toBe("Approved — submission blocked");
    const failed = payoutViewState(batch({ status: "FAILED", allowed_actions: [] }), ENABLED);
    expect([failed.headline, failed.tone]).toEqual(["Payout failed", "danger"]);
  });
});

describe("geography", () => {
  it("normalizes ZIP and ZIP+4", () => {
    expect(normalizePostalCode(" 10001 ")).toBe("10001");
    expect(normalizePostalCode("100011234")).toBe("10001-1234");
    expect(normalizePostalCode("1000")).toBeNull();
    expect(parsePostalCodeList("10001, 10002\n10001 abc")).toEqual({ codes: ["10001", "10002"], invalid: ["abc"] });
  });

  it("parses and validates import CSV locally", () => {
    const ok = parsePostalCodeCsv("postal_code,city,state_code,emergency_service_enabled,priority\n10001,New York,ny,yes,5\n10002,,,,\n");
    expect(ok.errors).toEqual([]);
    expect(ok.rows).toEqual([
      { postal_code: "10001", city: "New York", state_code: "NY", active: true, regular_service_enabled: true, emergency_service_enabled: true, priority: 5 },
      { postal_code: "10002", city: null, state_code: null, active: true, regular_service_enabled: true, emergency_service_enabled: false, priority: 100 },
    ]);
    const bad = parsePostalCodeCsv("postal_code,active,shoe_size\n10001,maybe\n1234\n10002\n10002\n");
    expect(bad.errors).toEqual([
      "Unknown columns: shoe_size.",
      "Line 2: boolean columns must be true/false.",
      'Line 3: invalid postal code "1234".',
      "Line 5: duplicate postal code 10002.",
    ]);
    expect(parsePostalCodeCsv("city\nNYC").errors).toEqual(["Header must include postal_code."]);
    expect(parsePostalCodeCsv("").errors).toEqual(["The file is empty."]);
  });

  it("builds a zone payload only with a coverage selector", () => {
    const base = { legal_entity_id: VENDOR, name: "Manhattan", state_code: "", city: "", postal_codes: "", priority: "", regular_service_enabled: true, emergency_enabled: false };
    expect(buildZoneCreatePayload(base).errors).toContain("Choose at least one coverage selector: postal codes, city or state.");
    const { payload, errors } = buildZoneCreatePayload({ ...base, postal_codes: "10001 10002", state_code: "ny" });
    expect(errors).toEqual([]);
    expect(payload).toMatchObject({ legal_entity_id: VENDOR, state_code: "NY", postal_codes: ["10001", "10002"], priority: 100, country_code: "US" });
  });

  it("describes coverage without exposing coordinates", () => {
    const text = describeCoverage({ center: { latitude: 40.7128, longitude: -74.006 }, radius_miles: 10, boundary_configured: true, postal_codes: ["10001"], city: null, state_code: "NY" }).join(" ");
    expect(text).toContain("Radius coverage: 10 mi");
    expect(text).not.toContain("40.7");
    expect(text).not.toContain("-74");
  });
});

describe("provider decisions", () => {
  it("only allows decisions while pending", () => {
    expect(allowedDecisions({ status: "PENDING" })).toEqual(["approve", "request-information", "reject"]);
    for (const status of ["DRAFT", "INFORMATION_REQUESTED", "APPROVED", "REJECTED"] as const) {
      expect(allowedDecisions({ status })).toEqual([]);
    }
  });

  it("validates reasons like the API", () => {
    expect(validateDecisionReason("no")).not.toBeNull();
    expect(validateDecisionReason("Missing insurance")).toBeNull();
    expect(validateDecisionReason("x".repeat(1001))).not.toBeNull();
  });

  it("flattens application sections", () => {
    expect(sectionRows({ legal_name: "Acme", ein: null })).toEqual([{ label: "legal name", value: "Acme" }, { label: "ein", value: "—" }]);
    expect(sectionRows(["10001"])).toEqual([{ label: "#1", value: "10001" }]);
    expect(sectionRows(null)).toEqual([]);
  });
});

describe("session and navigation", () => {
  it("accepts only admin and finance sessions", () => {
    const admin = parseSession(JSON.stringify({ access_token: "t", user: { email: "a@b.co", full_name: "A", role: "admin" } }));
    expect(admin && canUseAdminPortal(admin)).toBe(true);
    const provider = parseSession(JSON.stringify({ access_token: "t", user: { email: "a@b.co", full_name: "A", role: "vendor_admin" } }));
    expect(provider && canUseAdminPortal(provider)).toBe(false);
    expect(parseSession("{not json")).toBeNull();
    expect(parseSession(JSON.stringify({ user: {} }))).toBeNull();
  });

  it("highlights the most specific navigation entry", () => {
    expect(isActivePath("/", "/")).toBe(true);
    expect(isActivePath("/users/abc", "/users")).toBe(true);
    expect(isActivePath("/geography/postal-codes", "/geography")).toBe(false);
    expect(isActivePath("/geography/zones/1", "/geography")).toBe(true);
    expect(isActivePath("/finance/payouts/b1", "/finance")).toBe(false);
    expect(isActivePath("/finance/payouts/b1", "/finance/payouts")).toBe(true);
  });
});
