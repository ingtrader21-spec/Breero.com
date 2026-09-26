import { JOB_STATUSES, RISK_SEVERITIES, type JobStatus, type RiskSeverity } from "./types";

export interface QueueFilterState {
  statuses: JobStatus[];
  vendorId: string;
  workerId: string;
  serviceAreaId: string;
  unassignedOnly: boolean;
  atRiskOnly: boolean;
  severity: RiskSeverity | "";
  scheduledFrom: string;
  scheduledTo: string;
  limit: number;
  offset: number;
}

export const DEFAULT_QUEUE_FILTERS: QueueFilterState = {
  statuses: [],
  vendorId: "",
  workerId: "",
  serviceAreaId: "",
  unassignedOnly: false,
  atRiskOnly: false,
  severity: "",
  scheduledFrom: "",
  scheduledTo: "",
  limit: 50,
  offset: 0,
};

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const isStatus = (value: string): value is JobStatus => (JOB_STATUSES as readonly string[]).includes(value);
const isSeverity = (value: string): value is RiskSeverity => (RISK_SEVERITIES as readonly string[]).includes(value);

/** Datetime-local input values are the operator's local wall time; send them as UTC instants. */
function toInstant(value: string): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString();
}

/** Inverse of toInstant: an ISO instant rendered as a datetime-local input value. */
function toLocalInput(value: string | null): string {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())}T${pad(parsed.getHours())}:${pad(parsed.getMinutes())}`;
}

/** Serialize UI filter state into the canonical /control-center/queue query string. */
export function toQueueSearchParams(filters: QueueFilterState): URLSearchParams {
  const params = new URLSearchParams();
  for (const status of filters.statuses) params.append("status", status);
  if (UUID.test(filters.vendorId.trim())) params.set("vendor_id", filters.vendorId.trim());
  if (UUID.test(filters.workerId.trim())) params.set("worker_id", filters.workerId.trim());
  if (UUID.test(filters.serviceAreaId.trim())) params.set("service_area_id", filters.serviceAreaId.trim());
  if (filters.unassignedOnly) params.set("unassigned_only", "true");
  if (filters.atRiskOnly) params.set("at_risk_only", "true");
  if (filters.severity) params.set("severity", filters.severity);
  const from = toInstant(filters.scheduledFrom);
  const to = toInstant(filters.scheduledTo);
  if (from) params.set("scheduled_from", from);
  if (to) params.set("scheduled_to", to);
  params.set("limit", String(Math.min(Math.max(Math.trunc(filters.limit) || 50, 1), 200)));
  params.set("offset", String(Math.max(Math.trunc(filters.offset) || 0, 0)));
  return params;
}

/** Restore filter state from a page URL so queue views are linkable. */
export function fromSearchParams(params: URLSearchParams): QueueFilterState {
  const severity = params.get("severity") ?? "";
  const limit = Number(params.get("limit"));
  const offset = Number(params.get("offset"));
  return {
    ...DEFAULT_QUEUE_FILTERS,
    statuses: params.getAll("status").filter(isStatus),
    vendorId: params.get("vendor_id") ?? "",
    workerId: params.get("worker_id") ?? "",
    serviceAreaId: params.get("service_area_id") ?? "",
    unassignedOnly: params.get("unassigned_only") === "true",
    atRiskOnly: params.get("at_risk_only") === "true",
    severity: isSeverity(severity) ? severity : "",
    scheduledFrom: toLocalInput(params.get("scheduled_from")),
    scheduledTo: toLocalInput(params.get("scheduled_to")),
    limit: Number.isFinite(limit) && limit > 0 ? Math.min(limit, 200) : DEFAULT_QUEUE_FILTERS.limit,
    offset: Number.isFinite(offset) && offset > 0 ? offset : 0,
  };
}

/** Validation errors that must be fixed before the request is sent. */
export function queueFilterErrors(filters: QueueFilterState): string[] {
  const errors: string[] = [];
  for (const [label, value] of [["Vendor", filters.vendorId], ["Worker", filters.workerId], ["Service area", filters.serviceAreaId]] as const) {
    if (value.trim() && !UUID.test(value.trim())) errors.push(`${label} ID must be a UUID.`);
  }
  const from = toInstant(filters.scheduledFrom);
  const to = toInstant(filters.scheduledTo);
  if (from && to && to <= from) errors.push("Scheduled 'to' must be after 'from'.");
  return errors;
}
