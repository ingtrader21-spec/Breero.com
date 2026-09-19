import { describe, expect, it } from "vitest";
import type { AccessAssignmentInput, PortalContext } from "@breero/types";
import {
  assignmentLabel,
  assignmentsFromContext,
  validateAccessAssignments,
} from "./access-assignment-model";

const userId = "123e4567-e89b-42d3-a456-426614174000";
const validAssignment: AccessAssignmentInput = {
  role: "support",
  department: "customer_support",
  tenant_scope: "brand",
  vendor_id: null,
  is_primary: true,
};

describe("access assignment model", () => {
  it("accepts a valid assignment and summarizes it", () => {
    expect(validateAccessAssignments(userId, [validAssignment])).toEqual([]);
    expect(assignmentLabel(validAssignment)).toBe("support · customer_support · brand · primary");
  });

  it("rejects duplicate assignments, multiple primaries and invalid vendor scope", () => {
    const assignments: AccessAssignmentInput[] = [
      validAssignment,
      { ...validAssignment },
      {
        role: "vendor_admin",
        department: "provider",
        tenant_scope: "vendor",
        vendor_id: null,
        is_primary: false,
      },
    ];

    expect(validateAccessAssignments("not-a-uuid", assignments)).toEqual(expect.arrayContaining([
      "Enter a valid BREERO user UUID.",
      "Choose only one primary workspace.",
      "Remove the duplicate support/customer_support assignment.",
      "Vendor-scoped vendor_admin/provider access requires a vendor UUID.",
    ]));
  });

  it("copies server assignments into an editable payload", () => {
    const context: PortalContext = {
      user: {
        id: userId,
        email: "support@breero.test",
        full_name: "Support User",
        role: "operations",
        is_active: true,
        email_verified: true,
      },
      brand_key: "breero",
      dashboard_path: "/support",
      roles: ["support"],
      departments: ["customer_support"],
      permissions: ["support.customers.read"],
      assignments: [{
        role: "support",
        department: "customer_support",
        tenant_scope: "brand",
        vendor_id: null,
        is_primary: true,
      }],
      identity_mode: "keycloak",
    };

    expect(assignmentsFromContext(context)).toEqual([validAssignment]);
  });
});
