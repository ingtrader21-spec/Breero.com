import type { AccessAssignmentInput, PortalContext } from "@breero/types";

export const USER_UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function isValidUserId(value: string): boolean {
  return USER_UUID_PATTERN.test(value.trim());
}

export function assignmentsFromContext(context: PortalContext): AccessAssignmentInput[] {
  return context.assignments.map((assignment) => ({
    role: assignment.role,
    department: assignment.department,
    tenant_scope: assignment.tenant_scope,
    vendor_id: assignment.vendor_id,
    is_primary: assignment.is_primary,
  }));
}

export function validateAccessAssignments(
  userId: string,
  assignments: AccessAssignmentInput[],
): string[] {
  const errors: string[] = [];

  if (!isValidUserId(userId)) errors.push("Enter a valid BREERO user UUID.");
  if (!assignments.length) errors.push("Add at least one access assignment.");
  if (assignments.filter((assignment) => assignment.is_primary).length > 1) {
    errors.push("Choose only one primary workspace.");
  }

  const uniqueAssignments = new Set<string>();
  for (const assignment of assignments) {
    const assignmentKey = `${assignment.role}:${assignment.department}`;
    if (uniqueAssignments.has(assignmentKey)) {
      errors.push(`Remove the duplicate ${assignment.role}/${assignment.department} assignment.`);
    }
    uniqueAssignments.add(assignmentKey);

    if (assignment.tenant_scope === "vendor" && !assignment.vendor_id) {
      errors.push(`Vendor-scoped ${assignment.role}/${assignment.department} access requires a vendor UUID.`);
    }
    if (assignment.tenant_scope !== "vendor" && assignment.vendor_id) {
      errors.push(`Remove the vendor UUID from ${assignment.role}/${assignment.department} access or change its scope to Vendor.`);
    }
    if (assignment.vendor_id && !isValidUserId(assignment.vendor_id)) {
      errors.push(`Enter a valid vendor UUID for ${assignment.role}/${assignment.department} access.`);
    }
  }

  return [...new Set(errors)];
}

export function assignmentLabel(assignment: AccessAssignmentInput): string {
  const scope = assignment.tenant_scope === "vendor" && assignment.vendor_id
    ? `vendor ${assignment.vendor_id}`
    : assignment.tenant_scope;
  return `${assignment.role} · ${assignment.department} · ${scope}${assignment.is_primary ? " · primary" : ""}`;
}
