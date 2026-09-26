import type { AuditFilters, MetadataValue } from "./types";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const ACTION = /^[a-z0-9_]+(\.[a-z0-9_]+)*$/;
const ACTION_PREFIX = /^[a-z0-9_]+(\.[a-z0-9_]+)*\.?$/;
const RESOURCE_TYPE = /^[a-z_]{1,80}$/;
const TRACE_ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const DAY_MS = 86_400_000;
export const MAX_WINDOW_DAYS = 366;
export const MAX_PAGE_SIZE = 100;

export class AuditFilterError extends Error {}

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

/** Format a Date as a `datetime-local` input value in the browser's timezone. */
export function toLocalInput(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function defaultFilters(now: Date = new Date()): AuditFilters {
  return {
    view: "all",
    occurredFrom: toLocalInput(new Date(now.getTime() - 7 * DAY_MS)),
    occurredTo: toLocalInput(new Date(now.getTime() + 60_000)),
    actorId: "",
    action: "",
    actionIsPrefix: false,
    resourceType: "",
    resourceId: "",
    result: "",
    category: "",
    correlationId: "",
    vendorId: "",
    limit: 50,
  };
}

function toIso(localValue: string, label: string): string {
  const date = new Date(localValue);
  if (!localValue || Number.isNaN(date.getTime())) throw new AuditFilterError(`${label} is not a valid date and time.`);
  // toISOString always carries an explicit UTC offset, which the API requires.
  return date.toISOString();
}

function checked(value: string, pattern: RegExp, label: string): string | undefined {
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  if (!pattern.test(trimmed)) throw new AuditFilterError(`${label} has an invalid format.`);
  return trimmed;
}

/** Build validated query parameters. Throws AuditFilterError for out-of-contract input. */
export function buildSearchParams(filters: AuditFilters, cursor?: string | null): URLSearchParams {
  const from = toIso(filters.occurredFrom, "Start");
  const to = toIso(filters.occurredTo, "End");
  const span = Date.parse(to) - Date.parse(from);
  if (span <= 0) throw new AuditFilterError("Start must be earlier than end.");
  if (span > MAX_WINDOW_DAYS * DAY_MS) throw new AuditFilterError(`The search window may not exceed ${MAX_WINDOW_DAYS} days.`);
  if (!Number.isInteger(filters.limit) || filters.limit < 1 || filters.limit > MAX_PAGE_SIZE) {
    throw new AuditFilterError(`Page size must be between 1 and ${MAX_PAGE_SIZE}.`);
  }

  const params = new URLSearchParams({ occurred_from: from, occurred_to: to, limit: String(filters.limit) });
  const set = (key: string, value: string | undefined) => { if (value) params.set(key, value); };
  set("actor_id", checked(filters.actorId, UUID, "Actor ID"));
  set(filters.actionIsPrefix ? "action_prefix" : "action", checked(filters.action, filters.actionIsPrefix ? ACTION_PREFIX : ACTION, "Action"));
  set("resource_type", checked(filters.resourceType, RESOURCE_TYPE, "Resource type"));
  set("resource_id", checked(filters.resourceId, UUID, "Resource ID"));
  set("result", filters.result || undefined);
  set("category", filters.category || undefined);
  set("correlation_id", checked(filters.correlationId, TRACE_ID, "Correlation ID"));
  set("vendor_id", checked(filters.vendorId, UUID, "Provider ID"));
  if (cursor) params.set("cursor", cursor);
  return params;
}

export function listPath(filters: AuditFilters, cursor?: string | null): string {
  const base = filters.view === "security" ? "/admin/audit/security-events" : "/admin/audit/events";
  return `${base}?${buildSearchParams(filters, cursor).toString()}`;
}

export function detailPath(eventId: string): string {
  if (!UUID.test(eventId)) throw new AuditFilterError("Invalid event ID.");
  return `/admin/audit/events/${eventId}`;
}

export function tracePath(correlationId: string): string {
  if (!TRACE_ID.test(correlationId)) throw new AuditFilterError("Invalid correlation ID.");
  return `/admin/audit/correlations/${encodeURIComponent(correlationId)}`;
}

export function formatMetadataValue(value: MetadataValue): string {
  if (value === null) return "—";
  if (Array.isArray(value)) return value.length ? value.map(String).join(", ") : "—";
  return String(value);
}

export function humanize(value: string): string {
  return value.replaceAll("_", " ");
}
