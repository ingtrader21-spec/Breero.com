import { describe, expect, it } from "vitest";
import {
  canViewCaseScope,
  caseStatusLabel,
  effectiveAudience,
  escalationLabel,
  evidencePresentation,
  resolveStaffTenantScope,
  resolveSupportViewer,
  visibleCaseEntries,
  type SupportCaseEntry,
} from "./case-model";
import { assignment, caseEntries, customerContext, portalContext } from "./test-fixtures";

const ids = (entries: SupportCaseEntry[]) => entries.map((entry) => entry.id);

describe("resolveSupportViewer", () => {
  it("treats support staff with a read permission as staff with internal access", () => {
    expect(resolveSupportViewer(portalContext())).toEqual({ kind: "staff", canReadInternal: true });
  });

  it("treats trust & safety staff with audit read as staff", () => {
    const context = portalContext({ departments: ["trust_safety"], permissions: ["trust.audit.read"] });
    expect(resolveSupportViewer(context).kind).toBe("staff");
  });

  it("denies staff access to a support department without a read permission", () => {
    const context = portalContext({ permissions: ["support.customers.read"] });
    expect(resolveSupportViewer(context)).toEqual({ kind: "none", canReadInternal: false });
  });

  it("denies staff access to a read permission outside a support department", () => {
    const context = portalContext({ departments: ["finance"], permissions: ["support.communications.read"] });
    expect(resolveSupportViewer(context).kind).toBe("none");
  });

  it("honours the wildcard permission only together with a staff department", () => {
    expect(resolveSupportViewer(portalContext({ permissions: ["*"] })).kind).toBe("staff");
    expect(resolveSupportViewer(portalContext({ departments: ["administration"], permissions: ["*"] })).kind).toBe("none");
  });

  it("classifies customers and providers without internal access", () => {
    expect(resolveSupportViewer(customerContext)).toEqual({ kind: "customer", canReadInternal: false });
    const provider = portalContext({ departments: ["provider"], permissions: ["provider.jobs.read"] });
    expect(resolveSupportViewer(provider)).toEqual({ kind: "provider", canReadInternal: false });
  });
});

describe("tenant scope", () => {
  it("reports the widest support assignment scope", () => {
    const context = portalContext({
      assignments: [assignment({ tenant_scope: "vendor", vendor_id: "v1" }), assignment({ tenant_scope: "global" })],
    });
    expect(resolveStaffTenantScope(context)).toBe("global");
  });

  it("ignores assignments outside support departments", () => {
    const context = portalContext({ assignments: [assignment({ department: "finance", tenant_scope: "global" })] });
    expect(resolveStaffTenantScope(context)).toBe("none");
  });

  it("allows brand-scoped staff only inside their brand", () => {
    const context = portalContext();
    expect(canViewCaseScope(context, { brand_key: "breero", vendor_id: "v1" })).toBe(true);
    expect(canViewCaseScope(context, { brand_key: "other", vendor_id: "v1" })).toBe(false);
    expect(canViewCaseScope(context, { brand_key: "", vendor_id: null })).toBe(false);
  });

  it("limits vendor-scoped staff to their provider organization", () => {
    const context = portalContext({ assignments: [assignment({ tenant_scope: "vendor", vendor_id: "v1" })] });
    expect(canViewCaseScope(context, { brand_key: "breero", vendor_id: "v1" })).toBe(true);
    expect(canViewCaseScope(context, { brand_key: "breero", vendor_id: "v2" })).toBe(false);
    expect(canViewCaseScope(context, { brand_key: "breero", vendor_id: null })).toBe(false);
  });

  it("fails closed for a vendor assignment with no vendor id", () => {
    const context = portalContext({ assignments: [assignment({ tenant_scope: "vendor", vendor_id: null })] });
    expect(canViewCaseScope(context, { brand_key: "breero", vendor_id: null })).toBe(false);
  });

  it("never grants customers case scope in the browser", () => {
    expect(canViewCaseScope(customerContext, { brand_key: "breero", vendor_id: null })).toBe(false);
  });
});

describe("visibleCaseEntries", () => {
  it("shows staff every entry including internal notes", () => {
    expect(ids(visibleCaseEntries({ kind: "staff", canReadInternal: true }, caseEntries))).toEqual(
      ["m1", "m2", "n1", "n2", "e1", "e2", "s1", "x1"],
    );
  });

  it("hides internal entries from staff without internal access", () => {
    expect(ids(visibleCaseEntries({ kind: "staff", canReadInternal: false }, caseEntries))).toEqual(
      ["m1", "m2", "e1", "s1"],
    );
  });

  it("shows customers only customer-visible entries and never internal notes", () => {
    expect(ids(visibleCaseEntries({ kind: "customer", canReadInternal: false }, caseEntries))).toEqual(["m1", "e1", "s1"]);
  });

  it("shows providers only provider-visible entries", () => {
    expect(ids(visibleCaseEntries({ kind: "provider", canReadInternal: false }, caseEntries))).toEqual(["m2"]);
  });

  it("shows nothing to an unclassified viewer", () => {
    expect(visibleCaseEntries({ kind: "none", canReadInternal: false }, caseEntries)).toEqual([]);
  });

  it("drops entries with an unknown audience or kind", () => {
    const unknown = [
      { ...caseEntries[0], id: "u1", audience: "public" },
      { ...caseEntries[0], id: "u2", kind: "broadcast" },
    ] as unknown as SupportCaseEntry[];
    expect(visibleCaseEntries({ kind: "staff", canReadInternal: true }, unknown)).toEqual([]);
    expect(effectiveAudience(unknown[0])).toBeNull();
  });

  it("treats internal notes as internal whatever audience they carry", () => {
    expect(effectiveAudience(caseEntries[3])).toBe("internal");
  });
});

describe("presentation", () => {
  it("allows evidence download only after a clean scan", () => {
    expect(evidencePresentation("clean").downloadable).toBe(true);
    for (const state of ["pending", "quarantined", "rejected", "infected", ""]) {
      expect(evidencePresentation(state).downloadable).toBe(false);
    }
    expect(evidencePresentation("infected").label).toBe("Unverified file");
  });

  it("labels unknown statuses and escalations instead of guessing", () => {
    expect(caseStatusLabel("awaiting_customer")).toBe("Awaiting customer");
    expect(caseStatusLabel("reopened")).toBe("Unknown status");
    expect(escalationLabel("legal")).toBe("Legal review");
    expect(escalationLabel("police")).toBe("Unknown escalation");
  });
});
