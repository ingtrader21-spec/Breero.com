// Local mirror of the /api/v1/admin/audit OpenAPI schemas. Replace with the shared
// @breero/api-client types once Agent 5 publishes them (see README in this folder).

export type AuditResult = "success" | "denied" | "failure";

export const AUDIT_CATEGORIES = [
  "access_denied",
  "auth_lifecycle",
  "access_change",
  "privileged_admin",
  "provider_decision",
  "dispatch",
  "finance",
  "integration",
  "privacy",
  "domain",
] as const;
export type AuditCategory = (typeof AUDIT_CATEGORIES)[number];

export type MetadataValue = string | number | boolean | null | Array<string | number | boolean>;

export interface AuditEventSummary {
  id: string;
  occurred_at: string;
  category: AuditCategory;
  action: string;
  result: AuditResult;
  actor: { id: string | null; type: string };
  resource: { type: string; id: string };
  vendor_id: string | null;
  request_id: string | null;
  correlation_id: string | null;
  security_relevant: boolean;
}

export interface AuditEventDetail extends AuditEventSummary {
  metadata: Record<string, MetadataValue>;
  metadata_withheld_keys: number;
  source_fingerprint: string | null;
}

export interface AuditEventPage {
  items: AuditEventSummary[];
  next_cursor: string | null;
  limit: number;
  occurred_from: string;
  occurred_to: string;
}

export interface AuditCorrelationTrace {
  correlation_id: string;
  items: AuditEventDetail[];
  truncated: boolean;
}

export interface AuditFilters {
  view: "all" | "security";
  occurredFrom: string; // datetime-local value, interpreted in the browser's timezone
  occurredTo: string;
  actorId: string;
  action: string;
  actionIsPrefix: boolean;
  resourceType: string;
  resourceId: string;
  result: "" | AuditResult;
  category: "" | AuditCategory;
  correlationId: string;
  vendorId: string;
  limit: number;
}
