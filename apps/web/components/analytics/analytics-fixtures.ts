import type { MarketplaceMetrics, MetricGroup, MetricValue } from "@breero/types";

export const GENERATED_AT = "2026-09-23T12:00:00+00:00";

const count = (key: string, label: string, value: number): MetricValue => ({
  key, label, unit: "count", value, numerator: null, denominator: null,
});
const ratio = (key: string, label: string, numerator: number, denominator: number): MetricValue => ({
  key, label, unit: "ratio", value: denominator ? Number((numerator / denominator).toFixed(4)) : null, numerator, denominator,
});

const available = (key: MetricGroup["key"], label: string, values: MetricValue[], sources: string[]): MetricGroup => ({
  key, label, status: "available", reason: null, note: null, blocked_by: null, sources,
  source_watermark: "2026-09-23T11:45:00+00:00", values,
});

export function metricsFixture(overrides: Partial<MarketplaceMetrics> = {}): MarketplaceMetrics {
  return {
    scope: { kind: "marketplace", vendor_id: null },
    window: { start: "2026-08-24T12:00:00+00:00", end: GENERATED_AT },
    generated_at: GENERATED_AT,
    projection: { mode: "live_read_model", source_of_record: "postgresql", consistency: "repeatable_read_snapshot", max_age_seconds: 300 },
    groups: [
      available("booking", "Bookings", [
        count("bookings_created", "Bookings created", 4),
        ratio("confirmation_rate", "Confirmation rate", 2, 4),
      ], ["bookings"]),
      available("response_time", "Response time", [
        count("offers_responded", "Offers answered", 2),
        { key: "median_response_seconds", label: "Median response time", unit: "seconds", value: 180, numerator: null, denominator: null },
      ], ["dispatch_offers"]),
      {
        key: "finance", label: "Finance", status: "unavailable",
        reason: "Payment, ledger, earnings, and payout metrics require certified finance projections and stay withheld until then.",
        note: null, blocked_by: "PAS-129", sources: [], source_watermark: null, values: [],
      },
    ],
    ...overrides,
  };
}

export function providerFixture(): MarketplaceMetrics {
  const base = metricsFixture();
  return {
    ...base,
    scope: { kind: "provider", vendor_id: "123e4567-e89b-42d3-a456-426614174111" },
    groups: [
      {
        key: "request", label: "Requests", status: "restricted",
        reason: "Booking intents are anonymous until a provider is assigned, so they cannot be attributed to a provider organization.",
        note: null, blocked_by: null, sources: ["booking_intents"], source_watermark: null, values: [],
      },
      ...base.groups,
    ],
  };
}

export function emptyFixture(): MarketplaceMetrics {
  const base = metricsFixture();
  return {
    ...base,
    groups: [
      { ...base.groups[0], source_watermark: null, values: [count("bookings_created", "Bookings created", 0), ratio("confirmation_rate", "Confirmation rate", 0, 0)] },
      base.groups[2],
    ],
  };
}
