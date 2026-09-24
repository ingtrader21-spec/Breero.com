import type { ISODateTime, UUID } from "./index";

export type AnalyticsScopeKind = "marketplace" | "provider";
export type MetricGroupKey =
  | "request" | "qualification" | "matching" | "opportunity" | "quote" | "booking"
  | "utilization" | "completion" | "cancellation" | "review" | "response_time" | "finance";
/** available: computed from the source of record; unavailable: no certified source yet;
 * restricted: the source exists but cannot be attributed to the caller's tenant scope. */
export type MetricGroupStatus = "available" | "unavailable" | "restricted";
export type MetricUnit = "count" | "ratio" | "seconds";

export interface MetricValue {
  key: string;
  label: string;
  unit: MetricUnit;
  /** Null when undefined, e.g. a rate with a zero denominator. Never substitute a number. */
  value: number | null;
  numerator: number | null;
  denominator: number | null;
}

export interface MetricGroup {
  key: MetricGroupKey;
  label: string;
  status: MetricGroupStatus;
  reason: string | null;
  note: string | null;
  blocked_by: string | null;
  sources: string[];
  source_watermark: ISODateTime | null;
  values: MetricValue[];
}

export interface MarketplaceMetrics {
  scope: { kind: AnalyticsScopeKind; vendor_id: UUID | null };
  window: { start: ISODateTime; end: ISODateTime };
  generated_at: ISODateTime;
  projection: {
    mode: string;
    source_of_record: string;
    consistency: string;
    max_age_seconds: number;
  };
  groups: MetricGroup[];
}

export interface AnalyticsWindowQuery { start?: ISODateTime; end?: ISODateTime }
