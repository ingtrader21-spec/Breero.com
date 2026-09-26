import { afterEach, describe, expect, it, vi } from "vitest";

import { AuditApiError, auditGet, readAccessToken } from "./api";
import { AuditFilterError, buildSearchParams, defaultFilters, detailPath, formatMetadataValue, listPath, toLocalInput, tracePath } from "./query";
import type { AuditFilters } from "./types";

const NOW = new Date("2026-09-25T12:00:00Z");

function filters(overrides: Partial<AuditFilters> = {}): AuditFilters {
  return { ...defaultFilters(NOW), ...overrides };
}

describe("audit query building", () => {
  it("always sends an explicit, offset-bearing window and page size", () => {
    const params = buildSearchParams(filters());
    expect(params.get("occurred_from")).toMatch(/Z$/);
    expect(params.get("occurred_to")).toMatch(/Z$/);
    expect(params.get("limit")).toBe("50");
    expect([...params.keys()].sort()).toEqual(["limit", "occurred_from", "occurred_to"]);
  });

  it("maps every filter to the API contract", () => {
    const id = "0b6f3c1e-8a1d-4f59-9d2b-6f7f3a1d2c4e";
    const params = buildSearchParams(filters({
      actorId: id, action: "payout.", actionIsPrefix: true, resourceType: "payout_batch", resourceId: id,
      result: "denied", category: "access_denied", correlationId: "corr-1", vendorId: id, limit: 25,
    }), "CURSOR");
    expect(Object.fromEntries(params)).toMatchObject({
      actor_id: id, action_prefix: "payout.", resource_type: "payout_batch", resource_id: id,
      result: "denied", category: "access_denied", correlation_id: "corr-1", vendor_id: id, limit: "25", cursor: "CURSOR",
    });
    expect(params.has("action")).toBe(false);
  });

  it("rejects out-of-contract input before calling the API", () => {
    expect(() => buildSearchParams(filters({ actorId: "not-a-uuid" }))).toThrow(AuditFilterError);
    expect(() => buildSearchParams(filters({ action: "DROP TABLE" }))).toThrow(AuditFilterError);
    expect(() => buildSearchParams(filters({ correlationId: "bad id" }))).toThrow(AuditFilterError);
    expect(() => buildSearchParams(filters({ limit: 101 }))).toThrow(AuditFilterError);
    expect(() => buildSearchParams(filters({ occurredFrom: filters().occurredTo }))).toThrow(AuditFilterError);
    const tooOld = toLocalInput(new Date(NOW.getTime() - 400 * 86_400_000));
    expect(() => buildSearchParams(filters({ occurredFrom: tooOld }))).toThrow(/366 days/);
  });

  it("routes security view and builds safe detail and trace paths", () => {
    expect(listPath(filters({ view: "security" }))).toMatch(/^\/admin\/audit\/security-events\?/);
    expect(listPath(filters())).toMatch(/^\/admin\/audit\/events\?/);
    expect(() => detailPath("../../users")).toThrow(AuditFilterError);
    expect(() => tracePath("a/b")).toThrow(AuditFilterError);
    expect(tracePath("corr:1.2")).toBe("/admin/audit/correlations/corr%3A1.2");
  });

  it("formats metadata values without object serialization", () => {
    expect(formatMetadataValue(null)).toBe("—");
    expect(formatMetadataValue(["admin", "support"])).toBe("admin, support");
    expect(formatMetadataValue(false)).toBe("false");
  });
});

describe("audit transport", () => {
  afterEach(() => { vi.unstubAllEnvs(); });

  it("reads only a well-formed portal session token", () => {
    expect(readAccessToken({ getItem: () => JSON.stringify({ access_token: "t" }) })).toBe("t");
    expect(readAccessToken({ getItem: () => "{broken" })).toBeNull();
    expect(readAccessToken({ getItem: () => JSON.stringify({ access_token: 1 }) })).toBeNull();
    expect(readAccessToken({ getItem: () => null })).toBeNull();
  });

  it("requires an https API origin and sends the bearer token without cookies", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.test/api/v1/");
    const fetcher = vi.fn(async () => new Response(JSON.stringify({ ok: true }), { status: 200 }));
    await auditGet("/admin/audit/catalog", "secret-token", fetcher as unknown as typeof fetch);
    const [url, init] = fetcher.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("https://api.example.test/api/v1/admin/audit/catalog");
    expect(init.credentials).toBe("omit");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer secret-token");

    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://insecure.example.test");
    await expect(auditGet("/x", "t", fetcher as unknown as typeof fetch)).rejects.toThrow(/secure API origin/);
  });

  it("maps denials to a non-leaky message that never echoes the token", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.test");
    const fetcher = vi.fn(async () => new Response(JSON.stringify({ detail: "Insufficient permissions" }), { status: 403 }));
    const failure = auditGet("/admin/audit/events", "secret-token", fetcher as unknown as typeof fetch);
    await expect(failure).rejects.toBeInstanceOf(AuditApiError);
    await expect(failure).rejects.not.toThrow(/secret-token/);
    await expect(failure).rejects.toThrow(/not authorized/);
  });
});
