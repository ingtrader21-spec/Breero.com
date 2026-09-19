import { describe, expect, it } from "vitest";
import type { PortalContext } from "@breero/types";
import {
  evaluateDashboardModules,
  filterDashboardModules,
  moduleStateLabel,
  type DashboardModuleDefinition,
} from "./dashboard-model";

const context: PortalContext = {
  user: {
    id: "123e4567-e89b-42d3-a456-426614174000",
    email: "operator@breero.test",
    full_name: "Operations User",
    role: "operations",
    is_active: true,
    email_verified: true,
  },
  brand_key: "breero",
  dashboard_path: "/ops",
  roles: ["operations"],
  departments: ["dispatch"],
  permissions: ["ops.dispatch.read", "ops.bookings.read"],
  assignments: [{
    role: "operations",
    department: "dispatch",
    tenant_scope: "brand",
    vendor_id: null,
    is_primary: true,
  }],
  identity_mode: "keycloak",
};

const modules: DashboardModuleDefinition[] = [
  {
    title: "Dispatch queue",
    description: "Requests awaiting operational handling.",
    permission: "ops.dispatch.read",
    href: "/ops/dispatch",
  },
  {
    title: "Bookings",
    description: "Operational booking visibility.",
    permission: "ops.bookings.read",
  },
  {
    title: "Audit",
    description: "Operational audit records.",
    permission: "ops.audit.read",
  },
];

describe("dashboard model", () => {
  it("evaluates permission and destination states without hiding restricted modules", () => {
    const evaluated = evaluateDashboardModules(modules, context);

    expect(evaluated).toEqual([
      expect.objectContaining({ allowed: true, destination: "linked" }),
      expect.objectContaining({ allowed: true, destination: "overview" }),
      expect.objectContaining({ allowed: false, destination: "overview" }),
    ]);
    expect(evaluated.map(moduleStateLabel)).toEqual([
      "Ready to open",
      "Access enabled",
      "Permission required",
    ]);
  });

  it("searches titles, descriptions and permission identifiers", () => {
    const evaluated = evaluateDashboardModules(modules, context);

    expect(filterDashboardModules(evaluated, "dispatch", "all").map((item) => item.module.title)).toEqual(["Dispatch queue"]);
    expect(filterDashboardModules(evaluated, "visibility", "all").map((item) => item.module.title)).toEqual(["Bookings"]);
    expect(filterDashboardModules(evaluated, "ops.audit.read", "all").map((item) => item.module.title)).toEqual(["Audit"]);
  });

  it("filters available, restricted, linked and overview states", () => {
    const evaluated = evaluateDashboardModules(modules, context);

    expect(filterDashboardModules(evaluated, "", "available")).toHaveLength(2);
    expect(filterDashboardModules(evaluated, "", "restricted").map((item) => item.module.title)).toEqual(["Audit"]);
    expect(filterDashboardModules(evaluated, "", "linked").map((item) => item.module.title)).toEqual(["Dispatch queue"]);
    expect(filterDashboardModules(evaluated, "", "overview").map((item) => item.module.title)).toEqual(["Bookings"]);
  });
});
