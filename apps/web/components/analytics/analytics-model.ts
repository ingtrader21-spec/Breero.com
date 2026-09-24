import { ApiError } from "@breero/api-client";
import type { AnalyticsWindowQuery, MarketplaceMetrics, MetricGroup, MetricGroupStatus, MetricValue } from "@breero/types";

export type AnalyticsScope = "marketplace" | "provider";

export const WINDOW_PRESETS = [
  { days: 7, label: "Last 7 days" },
  { days: 30, label: "Last 30 days" },
  { days: 90, label: "Last 90 days" },
] as const;

export type WindowPresetDays = (typeof WINDOW_PRESETS)[number]["days"];

export type AnalyticsFailure =
  | { kind: "restricted"; title: string; message: string }
  | { kind: "error"; title: string; message: string };

const EMPTY_VALUE = "—";

/** The server resolves "end" from its own snapshot clock; only the start is client-derived. */
export function windowForPreset(days: number, now: Date): AnalyticsWindowQuery {
  return { start: new Date(now.getTime() - days * 86_400_000).toISOString() };
}

export function isStale(data: MarketplaceMetrics, now: Date): boolean {
  const generated = Date.parse(data.generated_at);
  if (Number.isNaN(generated)) return true;
  return now.getTime() - generated > data.projection.max_age_seconds * 1000;
}

export function unavailableGroups(data: MarketplaceMetrics): MetricGroup[] {
  return data.groups.filter((group) => group.status !== "available");
}

/** True when every available count is zero: the window holds no recorded activity. */
export function hasNoActivity(data: MarketplaceMetrics): boolean {
  const counts = data.groups
    .filter((group) => group.status === "available")
    .flatMap((group) => group.values.filter((value) => value.unit === "count"));
  return counts.length > 0 && counts.every((value) => value.value === 0);
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)} s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    const rest = Math.round(seconds - minutes * 60);
    return rest ? `${minutes} min ${rest} s` : `${minutes} min`;
  }
  const hours = Math.floor(minutes / 60);
  const restMinutes = minutes - hours * 60;
  return restMinutes ? `${hours} h ${restMinutes} min` : `${hours} h`;
}

export function formatMetricValue(metric: MetricValue): string {
  if (metric.value === null || !Number.isFinite(metric.value)) return EMPTY_VALUE;
  if (metric.unit === "ratio") return `${(metric.value * 100).toFixed(1)}%`;
  if (metric.unit === "seconds") return formatDuration(metric.value);
  return metric.value.toLocaleString("en-US");
}

/** Accessible explanation for a value, including why it may be missing. */
export function describeMetricValue(metric: MetricValue): string | undefined {
  if (metric.unit === "ratio" && metric.numerator !== null && metric.denominator !== null) {
    return metric.value === null
      ? "Not enough activity in this window to compute a rate"
      : `${metric.numerator.toLocaleString("en-US")} of ${metric.denominator.toLocaleString("en-US")}`;
  }
  if (metric.value === null) return "No activity in this window";
  return undefined;
}

export function formatTimestamp(value: string | null): string {
  if (!value) return "No recorded activity";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown";
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "UTC",
    timeZoneName: "short",
  }).format(date);
}

export const GROUP_STATUS_LABEL: Record<MetricGroupStatus, string> = {
  available: "Live",
  unavailable: "Not yet available",
  restricted: "Outside your scope",
};

export const GROUP_STATUS_VARIANT: Record<MetricGroupStatus, "success" | "warning" | "neutral"> = {
  available: "success",
  unavailable: "warning",
  restricted: "neutral",
};

export function classifyAnalyticsFailure(reason: unknown, scope: AnalyticsScope): AnalyticsFailure {
  if (reason instanceof ApiError) {
    if (reason.kind === "forbidden") {
      return {
        kind: "restricted",
        title: "Analytics access required",
        message: reason.code === "PROVIDER_SCOPE_REQUIRED"
          ? "Your account is not linked to a provider organization, so provider analytics cannot be scoped."
          : scope === "marketplace"
            ? "Marketplace analytics are limited to internal operations and administration assignments."
            : "Provider analytics are limited to members of a provider organization.",
      };
    }
    if (reason.kind === "authentication") {
      return { kind: "error", title: "Sign in required", message: "Your session has expired. Sign in again to view analytics." };
    }
    if (reason.kind === "validation") {
      return { kind: "error", title: "Invalid reporting window", message: "Choose a different reporting window and try again." };
    }
    if (reason.kind === "network" || reason.kind === "timeout" || reason.kind === "unavailable") {
      return { kind: "error", title: "Analytics are temporarily unavailable", message: "We could not reach the analytics service. Try again shortly." };
    }
  }
  return { kind: "error", title: "We couldn’t load analytics", message: "The request did not complete. Try again shortly." };
}
