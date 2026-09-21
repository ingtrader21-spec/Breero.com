import { describe, expect, it } from "vitest";

import { buildContentSecurityPolicy } from "./edge";
import { formatLabel, formatMoney } from "./index";

describe("portal edge policy", () => {
  it("binds production scripts to the request nonce and blocks framing", () => {
    const nonce = "4a12dfe9f30d42b7a4f53061f18a9991";
    const policy = buildContentSecurityPolicy(nonce, true);

    expect(policy).toContain(`script-src 'self' 'nonce-${nonce}'`);
    expect(policy).toContain("object-src 'none'");
    expect(policy).toContain("base-uri 'self'");
    expect(policy).toContain("frame-ancestors 'none'");
    expect(policy).toContain("form-action 'self'");
    expect(policy).toContain("upgrade-insecure-requests");
    expect(policy).not.toContain("'unsafe-eval'");
    expect(policy).not.toContain("script-src *");
  });

  it("does not allow a nonce to inject another directive", () => {
    expect(() => buildContentSecurityPolicy("valid; frame-src *", true)).toThrow();
  });
});

describe("portal presentation helpers", () => {
  it("formats machine labels without exposing raw separators", () => {
    expect(formatLabel("pending_configuration")).toBe("Pending Configuration");
    expect(formatLabel("failed-terminal")).toBe("Failed Terminal");
  });

  it("formats monetary minor units", () => {
    expect(formatMoney(12345, "USD")).toBe("$123.45");
  });
});
