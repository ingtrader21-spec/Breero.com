import type { CandidateBlockingReason, JobStatus, RiskCode, RiskSeverity } from "./types";

// Presentation only: labels and formatting. Business state always comes from the API.

export const STATUS_LABELS: Record<JobStatus, string> = {
  CREATED: "Created",
  MATCHING: "Matching",
  OFFERED: "Offered",
  ASSIGNED: "Assigned",
  EN_ROUTE: "En route",
  ON_SITE: "On site",
  DIAGNOSING: "Diagnosing",
  AWAITING_APPROVAL: "Awaiting approval",
  IN_PROGRESS: "In progress",
  COMPLETED: "Completed",
  CANCELLED: "Cancelled",
};

export const RISK_LABELS: Record<RiskCode, string> = {
  UNASSIGNED_START_PASSED: "Unassigned past start",
  UNASSIGNED_NEAR_START: "Unassigned near start",
  NO_LIVE_OFFERS: "No live offers",
  ASSIGNED_START_PASSED: "Late to depart",
  VISIT_OVERRUN: "Visit overrun",
  APPROVAL_STALLED: "Approval stalled",
  WORK_REQUEST_REVIEW_OVERDUE: "Work request review overdue",
  ASSIGNED_WORKER_UNDISPATCHABLE: "Worker undispatchable",
};

export const SEVERITY_LABELS: Record<RiskSeverity, string> = {
  CRITICAL: "Critical",
  HIGH: "High",
  MEDIUM: "Medium",
};

export const BLOCKING_REASON_LABELS: Record<CandidateBlockingReason, string> = {
  JOB_NOT_ASSIGNABLE: "Job is not assignable in its current state",
  WORKER_UNAVAILABLE: "Worker is marked unavailable",
  RESERVED_FOR_ANOTHER_WORKER: "Booking slot is reserved for another worker",
  CURRENTLY_ASSIGNED: "Already assigned to this job",
};

export const TECHNICIAN_COMMAND_LABELS: Record<string, string> = {
  "en-route": "Start travel (en route)",
  arrive: "Arrive on site",
  diagnose: "Begin diagnosis",
  start: "Start work",
};

export function statusLabel(status: string): string {
  return STATUS_LABELS[status as JobStatus] ?? status.replaceAll("_", " ").toLowerCase();
}

export function humanize(value: string): string {
  const text = value.replaceAll(/[._-]/g, " ").trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function formatDateTime(value: string | null | undefined, timeZone?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  const options: Intl.DateTimeFormatOptions = {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  };
  try {
    return new Intl.DateTimeFormat("en-US", {
      ...options,
      timeZone: timeZone ?? "UTC",
    }).format(date);
  } catch {
    return new Intl.DateTimeFormat("en-US", {
      ...options,
      timeZone: "UTC",
    }).format(date);
  }
}

/** Relative distance between an instant and the server-reported generation time. */
export function relativeTo(value: string, reference: string): string {
  const deltaMinutes = Math.round((new Date(value).getTime() - new Date(reference).getTime()) / 60_000);
  if (!Number.isFinite(deltaMinutes)) return "—";
  const magnitude = Math.abs(deltaMinutes);
  const unit = magnitude >= 1440 ? `${Math.round(magnitude / 1440)}d` : magnitude >= 60 ? `${Math.round(magnitude / 60)}h` : `${magnitude}m`;
  if (magnitude === 0) return "now";
  return deltaMinutes > 0 ? `in ${unit}` : `${unit} ago`;
}

export function formatMoney(minor: number, currency: string): string {
  try {
    return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(minor / 100);
  } catch {
    return `${(minor / 100).toFixed(2)} ${currency}`;
  }
}

export function locationLabel(location: { city: string | null; state_code: string | null; postal_code: string | null }): string {
  const place = [location.city, location.state_code].filter(Boolean).join(", ");
  return [place, location.postal_code].filter(Boolean).join(" ") || "—";
}

export function shortId(id: string): string {
  return id.slice(0, 8);
}
