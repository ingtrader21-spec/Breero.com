import { ApiError } from "@breero/api-client";
import { describe, expect, it } from "vitest";
import {
  classifyAnalyticsFailure,
  describeMetricValue,
  formatMetricValue,
  formatTimestamp,
  hasNoActivity,
  isStale,
  unavailableGroups,
  windowForPreset,
} from "./analytics-model";
import { GENERATED_AT, emptyFixture, metricsFixture, providerFixture } from "./analytics-fixtures";

const generated = new Date(GENERATED_AT);

describe("analytics model", () => {
  it("derives only the window start and leaves the end to the server snapshot", () => {
    expect(windowForPreset(7, generated)).toEqual({ start: "2026-09-16T12:00:00.000Z" });
  });

  it("marks data stale only after the projection max age", () => {
    const data = metricsFixture();
    expect(isStale(data, new Date(generated.getTime() + 300_000))).toBe(false);
    expect(isStale(data, new Date(generated.getTime() + 300_001))).toBe(true);
    expect(isStale({ ...data, generated_at: "not-a-date" }, generated)).toBe(true);
  });

  it("reports withheld and restricted groups as degraded", () => {
    expect(unavailableGroups(metricsFixture()).map((group) => group.key)).toEqual(["finance"]);
    expect(unavailableGroups(providerFixture()).map((group) => group.key)).toEqual(["request", "finance"]);
  });

  it("detects windows with no recorded activity", () => {
    expect(hasNoActivity(emptyFixture())).toBe(true);
    expect(hasNoActivity(metricsFixture())).toBe(false);
  });

  it("formats values without inventing numbers for undefined rates", () => {
    const base = { key: "k", label: "L", numerator: null, denominator: null };
    expect(formatMetricValue({ ...base, unit: "count", value: 12_345 })).toBe("12,345");
    expect(formatMetricValue({ ...base, unit: "ratio", value: 0.3333 })).toBe("33.3%");
    expect(formatMetricValue({ ...base, unit: "seconds", value: 45 })).toBe("45 s");
    expect(formatMetricValue({ ...base, unit: "seconds", value: 180 })).toBe("3 min");
    expect(formatMetricValue({ ...base, unit: "seconds", value: 7_500 })).toBe("2 h 5 min");
    expect(formatMetricValue({ ...base, unit: "ratio", value: null, numerator: 0, denominator: 0 })).toBe("—");
    expect(describeMetricValue({ ...base, unit: "ratio", value: null, numerator: 0, denominator: 0 }))
      .toBe("Not enough activity in this window to compute a rate");
    expect(describeMetricValue({ ...base, unit: "ratio", value: 0.5, numerator: 2, denominator: 4 })).toBe("2 of 4");
  });

  it("formats timestamps in UTC and labels missing watermarks", () => {
    expect(formatTimestamp(GENERATED_AT)).toBe("Sep 23, 2026, 12:00 PM UTC");
    expect(formatTimestamp(null)).toBe("No recorded activity");
  });

  it("maps permission and scope failures to a restricted state", () => {
    const forbidden = new ApiError("Forbidden", "forbidden", 403, "ANALYTICS_SCOPE_DENIED");
    expect(classifyAnalyticsFailure(forbidden, "marketplace")).toMatchObject({ kind: "restricted" });
    const noProvider = new ApiError("Forbidden", "forbidden", 403, "PROVIDER_SCOPE_REQUIRED");
    expect(classifyAnalyticsFailure(noProvider, "provider").message).toContain("not linked to a provider organization");
    expect(classifyAnalyticsFailure(new ApiError("Down", "unavailable", 503), "marketplace")).toMatchObject({
      kind: "error", title: "Analytics are temporarily unavailable",
    });
    expect(classifyAnalyticsFailure(new Error("boom"), "marketplace").kind).toBe("error");
  });
});
