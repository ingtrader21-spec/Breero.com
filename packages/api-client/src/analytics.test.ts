import { describe, expect, it, vi } from "vitest";
import { createBreeroApi } from "./client";
import { createMockBreeroApi } from "./mock";

describe("analytics client", () => {
  it("reads scoped projections with an optional window and never mutates", async () => {
    const fetcher = vi.fn(async () => new Response("{}", { status: 200 }));
    const api = createBreeroApi({ baseUrl: "https://api.test/api/v1", fetch: fetcher as typeof fetch });
    await api.analytics.marketplace();
    await api.analytics.provider({ start: "2026-09-01T00:00:00+00:00", end: "2026-09-08T00:00:00+00:00" });
    const calls = fetcher.mock.calls as unknown as Array<[URL | RequestInfo, RequestInit]>;
    const urls = calls.map(([url]) => new URL(String(url)));
    expect(urls.map((url) => url.pathname)).toEqual([
      "/api/v1/analytics/marketplace/metrics",
      "/api/v1/analytics/provider/metrics",
    ]);
    expect(urls[0].search).toBe("");
    expect(urls[1].searchParams.get("start")).toBe("2026-09-01T00:00:00+00:00");
    expect(urls[1].searchParams.get("end")).toBe("2026-09-08T00:00:00+00:00");
    for (const [, init] of calls) expect(init.method ?? "GET").toBe("GET");
  });

  it("refuses to synthesize analytics in mock mode", async () => {
    const api = createMockBreeroApi();
    await expect(api.analytics.marketplace()).rejects.toThrow("marketplaceMetrics");
    await expect(api.analytics.provider()).rejects.toThrow("providerMetrics");
  });
});
