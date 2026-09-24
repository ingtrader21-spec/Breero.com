import type { AccessAssignment, Department, PortalContext } from "@breero/types";

/**
 * Frontend presentation policy for support / trust & safety cases (PAS-127, M20).
 *
 * The BREERO API does not yet expose SupportCase endpoints (see ./case-contract.ts),
 * so these types are the view model the UI renders, not a backend schema. The
 * backend remains the authority for access; everything here only narrows what a
 * browser may display and fails closed on anything it does not recognise.
 */

export type SupportCaseStatus =
  | "open"
  | "awaiting_customer"
  | "awaiting_provider"
  | "escalated"
  | "resolved"
  | "closed";

export type CaseEntryAudience = "customer" | "provider" | "internal";

export type CaseEntryKind = "message" | "internal_note" | "evidence" | "status_change" | "escalation";

export type EvidenceScanState = "pending" | "clean" | "quarantined" | "rejected";

export type EscalationLevel = "tier_2" | "trust_safety" | "legal";

export interface SupportCaseScope {
  brand_key: string;
  vendor_id: string | null;
}

export interface SupportCaseEntry {
  id: string;
  kind: CaseEntryKind;
  audience: CaseEntryAudience;
  author_label: string;
  occurred_at: string;
  body?: string;
  evidence?: { file_name: string; scan_state: EvidenceScanState };
  status_change?: { from: SupportCaseStatus; to: SupportCaseStatus };
  escalation?: { level: EscalationLevel; reason: string };
}

export type SupportViewerKind = "staff" | "customer" | "provider" | "none";

export interface SupportViewer {
  kind: SupportViewerKind;
  canReadInternal: boolean;
}

const STAFF_DEPARTMENTS: readonly Department[] = ["customer_support", "trust_safety"];
const STAFF_READ_PERMISSIONS = ["support.communications.read", "trust.audit.read"];
const KNOWN_AUDIENCES: ReadonlySet<string> = new Set<CaseEntryAudience>(["customer", "provider", "internal"]);
const KNOWN_KINDS: ReadonlySet<string> = new Set<CaseEntryKind>([
  "message",
  "internal_note",
  "evidence",
  "status_change",
  "escalation",
]);

function hasPermission(context: PortalContext, permission: string): boolean {
  return context.permissions.includes("*") || context.permissions.includes(permission);
}

function isStaffAssignment(assignment: AccessAssignment): boolean {
  return STAFF_DEPARTMENTS.includes(assignment.department);
}

/**
 * Classifies the signed-in user for support-case rendering. Staff need both a
 * support/trust department and an existing read permission; a department alone
 * is not enough. Anything else falls through to the narrowest audience.
 */
export function resolveSupportViewer(context: PortalContext): SupportViewer {
  const staffDepartment = context.departments.some((item) => STAFF_DEPARTMENTS.includes(item));
  const staffPermission = STAFF_READ_PERMISSIONS.some((permission) => hasPermission(context, permission));
  if (staffDepartment && staffPermission) return { kind: "staff", canReadInternal: true };
  if (context.departments.includes("customer")) return { kind: "customer", canReadInternal: false };
  if (context.departments.includes("provider")) return { kind: "provider", canReadInternal: false };
  return { kind: "none", canReadInternal: false };
}

export type StaffTenantScope = "global" | "brand" | "vendor" | "none";

/** Widest tenant scope granted by the viewer's support/trust assignments. */
export function resolveStaffTenantScope(context: PortalContext): StaffTenantScope {
  const scopes = context.assignments.filter(isStaffAssignment).map((item) => item.tenant_scope);
  if (scopes.includes("global")) return "global";
  if (scopes.includes("brand")) return "brand";
  if (scopes.includes("vendor")) return "vendor";
  return "none";
}

/**
 * Staff may only open a case inside a tenant their support/trust assignment
 * covers. Customer and provider ownership cannot be proven in the browser, so
 * they are always denied here and must rely on the API's record policy.
 */
export function canViewCaseScope(context: PortalContext, scope: SupportCaseScope): boolean {
  if (resolveSupportViewer(context).kind !== "staff") return false;
  if (!scope.brand_key || scope.brand_key !== context.brand_key) return false;
  return context.assignments.filter(isStaffAssignment).some((assignment) => {
    if (assignment.tenant_scope === "global" || assignment.tenant_scope === "brand") return true;
    if (assignment.tenant_scope === "vendor") {
      return assignment.vendor_id !== null && assignment.vendor_id === scope.vendor_id;
    }
    return false;
  });
}

/** Internal notes are always internal, whatever audience they were tagged with. */
export function effectiveAudience(entry: SupportCaseEntry): CaseEntryAudience | null {
  if (!KNOWN_KINDS.has(entry.kind) || !KNOWN_AUDIENCES.has(entry.audience)) return null;
  if (entry.kind === "internal_note") return "internal";
  return entry.audience;
}

export function visibleCaseEntries(viewer: SupportViewer, entries: readonly SupportCaseEntry[]): SupportCaseEntry[] {
  return entries.filter((entry) => {
    const audience = effectiveAudience(entry);
    if (audience === null) return false;
    if (viewer.kind === "staff") return audience !== "internal" || viewer.canReadInternal;
    if (viewer.kind === "customer") return audience === "customer";
    if (viewer.kind === "provider") return audience === "provider";
    return false;
  });
}

type BadgeVariant = "neutral" | "brand" | "success" | "warning" | "danger";

export function audiencePresentation(audience: CaseEntryAudience): { label: string; variant: BadgeVariant } {
  if (audience === "customer") return { label: "Visible to customer", variant: "brand" };
  if (audience === "provider") return { label: "Visible to provider", variant: "brand" };
  return { label: "Internal note — not shared", variant: "warning" };
}

export function evidencePresentation(state: string): { label: string; variant: BadgeVariant; downloadable: boolean } {
  if (state === "clean") return { label: "Scanned clean", variant: "success", downloadable: true };
  if (state === "pending") return { label: "Scan pending", variant: "neutral", downloadable: false };
  if (state === "quarantined") return { label: "Quarantined", variant: "danger", downloadable: false };
  if (state === "rejected") return { label: "Rejected", variant: "danger", downloadable: false };
  return { label: "Unverified file", variant: "danger", downloadable: false };
}

const STATUS_LABELS: Record<SupportCaseStatus, string> = {
  open: "Open",
  awaiting_customer: "Awaiting customer",
  awaiting_provider: "Awaiting provider",
  escalated: "Escalated",
  resolved: "Resolved",
  closed: "Closed",
};

export function caseStatusLabel(status: string): string {
  return STATUS_LABELS[status as SupportCaseStatus] ?? "Unknown status";
}

const ESCALATION_LABELS: Record<EscalationLevel, string> = {
  tier_2: "Tier 2 support",
  trust_safety: "Trust & safety",
  legal: "Legal review",
};

export function escalationLabel(level: string): string {
  return ESCALATION_LABELS[level as EscalationLevel] ?? "Unknown escalation";
}
