import { describe, expect, it } from "vitest";
import { resolveApiBase } from "./config";
import { formatMoney, locationLabel, relativeTo, statusLabel } from "./format";

describe("resolveApiBase", () => {
  it("accepts HTTPS origins and trims the trailing slash", () => {
    expect(resolveApiBase({ NEXT_PUBLIC_API_BASE_URL: "https://api.breero.com/api/v1/", NODE_ENV: "production" })).toBe("https://api.breero.com/api/v1");
  });

  it("allows a local HTTP API only outside production", () => {
    expect(resolveApiBase({ NEXT_PUBLIC_API_BASE_URL: "http://localhost:8000/api/v1", NODE_ENV: "development" })).toBe("http://localhost:8000/api/v1");
    expect(() => resolveApiBase({ NEXT_PUBLIC_API_BASE_URL: "http://localhost:8000/api/v1", NODE_ENV: "production" })).toThrow("secure");
  });

  it.each(["", "http://api.breero.com/api/v1", "http://localhost.evil.test/api/v1", "ftp://api.breero.com"])("rejects %s", (value) => {
    expect(() => resolveApiBase({ NEXT_PUBLIC_API_BASE_URL: value, NODE_ENV: "development" })).toThrow();
  });
});

describe("presentation formatting", () => {
  it("labels statuses without inventing new ones", () => {
    expect(statusLabel("AWAITING_APPROVAL")).toBe("Awaiting approval");
    expect(statusLabel("SOMETHING_NEW")).toBe("something new");
  });

  it("formats relative time against the server generation instant", () => {
    const reference = "2026-09-25T12:00:00Z";
    expect(relativeTo("2026-09-25T12:30:00Z", reference)).toBe("in 30m");
    expect(relativeTo("2026-09-25T09:00:00Z", reference)).toBe("3h ago");
    expect(relativeTo("2026-09-27T12:00:00Z", reference)).toBe("in 2d");
    expect(relativeTo("2026-09-25T12:00:10Z", reference)).toBe("now");
  });

  it("formats money and area-level locations", () => {
    expect(formatMoney(12345, "USD")).toBe("$123.45");
    expect(locationLabel({ city: "Austin", state_code: "TX", postal_code: "78701" })).toBe("Austin, TX 78701");
    expect(locationLabel({ city: null, state_code: null, postal_code: null })).toBe("—");
  });
});
