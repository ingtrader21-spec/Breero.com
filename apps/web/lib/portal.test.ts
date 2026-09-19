import { describe, expect, it, vi } from "vitest";
import { customerApi } from "./customer/api";
import {
  ACCESS_DENIED_DASHBOARD,
  assertAllowedDashboard,
  resolveUnauthorizedPortalDestination,
  routeToPortal,
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

  it.each([
    ["/account", "/account/bookings?status=open", "/account/bookings?status=open"],
    ["/support", "/account/bookings", "/support"],
    ["/account", "/admin", "/account"],
    ["/account", "//attacker.example/account", "/account"],
    ["/account", "/\\attacker.example/account", "/account"],
    ["/account", "/account/../admin", "/account"],
    ["/account", "/accounting", "/account"],
    ["/access-denied", "/account", "/access-denied"],
  ])("routes %s with return path %s to %s", async (dashboard, returnTo, expected) => {
    const replace = vi.fn();
    vi.stubGlobal("location", { origin: "https://breero.test", pathname: "/account/login", replace });
    vi.spyOn(customerApi.auth, "context").mockResolvedValue({ dashboard_path: dashboard } as Awaited<ReturnType<typeof customerApi.auth.context>>);
    try {
      await routeToPortal(returnTo);
      expect(replace).toHaveBeenCalledWith(expected);
    } finally {
      vi.restoreAllMocks();
      vi.unstubAllGlobals();
    }
  });
});
