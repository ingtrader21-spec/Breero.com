import type { AccessAssignment, PortalContext } from "@breero/types";
import type { SupportCaseEntry } from "./case-model";

export function portalContext(overrides: Partial<PortalContext> = {}): PortalContext {
  return {
    user: {
      id: "123e4567-e89b-42d3-a456-426614174000",
      email: "agent@breero.test",
      full_name: "Support Agent",
      role: "operations",
      is_active: true,
      email_verified: true,
    },
    brand_key: "breero",
    dashboard_path: "/support",
    roles: ["support"],
    departments: ["customer_support"],
    permissions: ["support.communications.read", "support.requests.read"],
    assignments: [assignment()],
    identity_mode: "keycloak",
    ...overrides,
  };
}

export function assignment(overrides: Partial<AccessAssignment> = {}): AccessAssignment {
  return {
    role: "support",
    department: "customer_support",
    tenant_scope: "brand",
    vendor_id: null,
    is_primary: true,
    ...overrides,
  };
}

export const customerContext = portalContext({
  dashboard_path: "/account",
  roles: ["customer"],
  departments: ["customer"],
  permissions: ["customer.profile.read"],
  assignments: [assignment({ role: "customer", department: "customer" })],
});

export const caseEntries: SupportCaseEntry[] = [
  { id: "m1", kind: "message", audience: "customer", author_label: "Customer", occurred_at: "2026-09-20T10:00:00Z", body: "The technician did not arrive." },
  { id: "m2", kind: "message", audience: "provider", author_label: "Provider", occurred_at: "2026-09-20T10:05:00Z", body: "We were delayed by traffic." },
  { id: "n1", kind: "internal_note", audience: "internal", author_label: "Support agent", occurred_at: "2026-09-20T10:10:00Z", body: "Second complaint this month for this provider." },
  { id: "n2", kind: "internal_note", audience: "customer", author_label: "Support agent", occurred_at: "2026-09-20T10:11:00Z", body: "Mis-tagged private note." },
  { id: "e1", kind: "evidence", audience: "customer", author_label: "Customer", occurred_at: "2026-09-20T10:15:00Z", evidence: { file_name: "doorbell.jpg", scan_state: "clean" } },
  { id: "e2", kind: "evidence", audience: "internal", author_label: "Trust & safety", occurred_at: "2026-09-20T10:16:00Z", evidence: { file_name: "invoice.pdf", scan_state: "quarantined" } },
  { id: "s1", kind: "status_change", audience: "customer", author_label: "Support agent", occurred_at: "2026-09-20T10:20:00Z", status_change: { from: "open", to: "escalated" } },
  { id: "x1", kind: "escalation", audience: "internal", author_label: "Support agent", occurred_at: "2026-09-20T10:21:00Z", escalation: { level: "trust_safety", reason: "Repeated no-show." } },
];
