import type { AccessAssignment, AccessRole, Department, TenantScope } from "./types";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Suggested department for each role; operators may still pick another. */
export const DEFAULT_DEPARTMENT: Record<AccessRole, Department> = {
  customer: "customer",
  vendor_admin: "provider",
  technician: "field_service",
  operations: "dispatch",
  ops_manager: "dispatch",
  support: "customer_support",
  finance: "finance",
  quality: "quality",
  trust_safety: "trust_safety",
  sales: "sales",
  marketing: "marketing",
  admin: "administration",
  superadmin: "administration",
};

export const PRIVILEGED_ROLES: readonly AccessRole[] = ["admin", "superadmin"];

export function newAssignment(role: AccessRole, isPrimary = false): AccessAssignment {
  return {
    role,
    department: DEFAULT_DEPARTMENT[role],
    tenant_scope: role === "admin" || role === "superadmin" ? "global" : "brand",
    vendor_id: null,
    is_primary: isPrimary,
  };
}

export function setScope(assignment: AccessAssignment, scope: TenantScope, vendorId: string | null = null): AccessAssignment {
  return { ...assignment, tenant_scope: scope, vendor_id: scope === "vendor" ? vendorId : null };
}

/** Mirrors the API's AccessProfileUpdate validation so errors surface before submit. */
export function validateAssignments(assignments: AccessAssignment[]): string[] {
  const errors: string[] = [];
  if (assignments.length > 32) errors.push("At most 32 assignments are allowed.");
  if (assignments.filter((item) => item.is_primary).length > 1) errors.push("Only one assignment can be primary.");
  const seen = new Set<string>();
  assignments.forEach((item, index) => {
    const key = `${item.role}:${item.department}`;
    if (seen.has(key)) errors.push(`Assignment ${index + 1} duplicates ${item.role} in ${item.department}.`);
    seen.add(key);
    if (item.tenant_scope === "vendor" && !(item.vendor_id && UUID_RE.test(item.vendor_id))) {
      errors.push(`Assignment ${index + 1} needs a valid vendor ID for vendor scope.`);
    }
    if (item.tenant_scope !== "vendor" && item.vendor_id) {
      errors.push(`Assignment ${index + 1} can only carry a vendor ID in vendor scope.`);
    }
  });
  return errors;
}

export function validateReason(reason: string): string | null {
  const trimmed = reason.trim();
  if (trimmed.length < 3) return "A reason of at least 3 characters is required.";
  if (trimmed.length > 500) return "Reason must be 500 characters or fewer.";
  return null;
}

export function grantsPrivilege(assignments: AccessAssignment[]): boolean {
  return assignments.some((item) => PRIVILEGED_ROLES.includes(item.role));
}

/** Human summary of a pending access change for the confirmation dialog. */
export function describeAccessChange(before: AccessAssignment[], after: AccessAssignment[]): { added: AccessRole[]; removed: AccessRole[] } {
  const beforeRoles = new Set(before.map((item) => item.role));
  const afterRoles = new Set(after.map((item) => item.role));
  return {
    added: [...afterRoles].filter((role) => !beforeRoles.has(role)),
    removed: [...beforeRoles].filter((role) => !afterRoles.has(role)),
  };
}
