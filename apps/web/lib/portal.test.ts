import { describe, expect, it } from "vitest";
import {
  ACCESS_DENIED_DASHBOARD,
  assertAllowedDashboard,
  resolveUnauthorizedPortalDestination,
} from "./portal";

describe("portal routing", () => {
  it("accepts the backend no-access dashboard as a fail-closed destination", () => {
    expect(() => assertAllowedDashboard(ACCESS_DENIED_DASHBOARD)).not.toThrow();
  });

  it("rejects an unknown dashboard supplied by an invalid portal context", () => {
    expect(() => assertAllowedDashboard("https://attacker.example/redirect")).toThrow(
      "Account dashboard is not configured",
    );
  });

  it("escapes an unauthorized redirect back to the current dashboard", () => {
    expect(resolveUnauthorizedPortalDestination("/support", "/support")).toBe(
      ACCESS_DENIED_DASHBOARD,
    );
  });

  it("preserves a different authorized dashboard destination", () => {
    expect(resolveUnauthorizedPortalDestination("/ops", "/support")).toBe("/ops");
  });
});
