import { describe, expect, it } from "vitest";

import { buildContentSecurityPolicy } from "./edge";
import { isAllowedPortalRequest, safeReturnTo } from "./server";
import type { PortalRuntimeConfig } from "./types";

const config: PortalRuntimeConfig = {
  kind: "partner",
  title: "Partner",
  eyebrow: "Provider workspace",
  allowedRoles: ["vendor_admin"],
  apiRules: [
    { prefix: "/portal/provider", methods: ["GET"] },
    { prefix: "/provider/services", methods: ["GET", "POST"] },
  ],
};

describe("portal routing safety", () => {
  it("accepts only relative return paths", () => {
    expect(safeReturnTo("/jobs?status=active")).toBe("/jobs?status=active");
    expect(safeReturnTo("https://evil.example/path")).toBe("/");
    expect(safeReturnTo("//evil.example/path")).toBe("/");
    expect(safeReturnTo("/%5c%5cevil.example")).toBe("/");
  });

  it("enforces both prefix and method allowlists", () => {
    expect(isAllowedPortalRequest("/portal/provider/overview", "GET", config)).toBe(true);
    expect(isAllowedPortalRequest("/portal/provider/overview", "POST", config)).toBe(false);
    expect(isAllowedPortalRequest("/provider/services", "POST", config)).toBe(true);
    expect(isAllowedPortalRequest("/finance/payout-batches", "GET", config)).toBe(false);
  });

  it("creates a nonce-bound restrictive policy", () => {
    const nonce = "abc123_DEF456-ghi";
    const policy = buildContentSecurityPolicy(nonce);
    expect(policy).toContain(`script-src 'self' 'nonce-${nonce}' 'strict-dynamic'`);
    expect(policy).toContain("frame-ancestors 'none'");
    expect(policy).toContain("object-src 'none'");
  });
});
