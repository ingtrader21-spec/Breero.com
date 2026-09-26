import { describe, expect, it, vi } from "vitest";
import { ApiError, createAdminApi, ifMatch, newIdempotencyKey, resolveApiBase, toApiError, withQuery } from "../lib/api";

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function client(response: Response | (() => Response)) {
  const fetchImpl = vi.fn(async () => (typeof response === "function" ? response() : response));
  const api = createAdminApi({ baseUrl: "https://api.example.test/api/v1", token: "tok", fetchImpl: fetchImpl as unknown as typeof fetch });
  return { api, fetchImpl };
}

type FetchCall = [string, RequestInit & { headers: Headers }];

function lastCall(fetchImpl: { mock: { calls: unknown[][] } }): { url: string; init: FetchCall[1] } {
  const [url, init] = fetchImpl.mock.calls.at(-1) as unknown as FetchCall;
  return { url, init };
}

describe("resolveApiBase", () => {
  it("accepts only https origins and strips a trailing slash", () => {
    expect(resolveApiBase("https://api.breero.com/api/v1/")).toBe("https://api.breero.com/api/v1");
    expect(() => resolveApiBase("http://api.breero.com")).toThrow("secure API origin");
    expect(() => resolveApiBase(undefined)).toThrow();
  });
});

describe("toApiError", () => {
  it("maps V1 domain errors", async () => {
    const error = await toApiError(json(409, { error: { code: "USER_ALREADY_DISABLED", message: "User is already disabled." } }));
    expect(error).toBeInstanceOf(ApiError);
    expect([error.status, error.code, error.message]).toEqual([409, "USER_ALREADY_DISABLED", "User is already disabled."]);
  });

  it("maps HTTPException detail strings", async () => {
    const error = await toApiError(json(403, { detail: "Insufficient permissions" }));
    expect([error.status, error.code, error.message]).toEqual([403, "HTTP_403", "Insufficient permissions"]);
  });

  it("maps FastAPI validation arrays to a readable message", async () => {
    const error = await toApiError(json(422, { detail: [{ loc: ["body", "reason"], msg: "String should have at least 3 characters" }] }));
    expect(error.code).toBe("VALIDATION_ERROR");
    expect(error.message).toBe("reason: String should have at least 3 characters");
  });

  it("falls back when the body is not JSON", async () => {
    const error = await toApiError(new Response("oops", { status: 502 }));
    expect(error.message).toBe("Request failed (502)");
  });
});

describe("helpers", () => {
  it("drops empty query values", () => {
    expect(withQuery("/admin/users", { q: "ann", status: undefined, role: "", page: 2, active: false })).toBe("/admin/users?q=ann&page=2&active=false");
    expect(withQuery("/x")).toBe("/x");
  });

  it("formats If-Match and idempotency keys the API accepts", () => {
    expect(ifMatch(7)).toBe('"7"');
    const key = newIdempotencyKey("postal-import", () => "0f8fad5b-d9cb-469f-a165-70867728950e");
    expect(key).toMatch(/^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$/);
  });
});

describe("createAdminApi", () => {
  it("sends bearer auth and never caches", async () => {
    const { api, fetchImpl } = client(json(200, { items: [], total: 0, page: 1, page_size: 25 }));
    await api.listUsers({ q: "a@b.co", status: "disabled", page: 1, page_size: 25 });
    const { url, init } = lastCall(fetchImpl);
    expect(url).toBe("https://api.example.test/api/v1/admin/users?q=a%40b.co&status=disabled&page=1&page_size=25");
    expect(init.headers.get("Authorization")).toBe("Bearer tok");
    expect(init.cache).toBe("no-store");
  });

  it("posts lifecycle reasons as JSON", async () => {
    const { api, fetchImpl } = client(json(200, { id: "u1" }));
    await api.disableUser("u1", "fraud review");
    const { url, init } = lastCall(fetchImpl);
    expect(url).toMatch(/\/admin\/users\/u1\/disable$/);
    expect(init.method).toBe("POST");
    expect(init.headers.get("Content-Type")).toBe("application/json");
    expect(JSON.parse(String(init.body))).toEqual({ reason: "fraud review" });
  });

  it("sends If-Match for versioned geography writes and handles 204", async () => {
    const { api, fetchImpl } = client(new Response(null, { status: 204 }));
    await expect(api.deactivateZone("z1", 4)).resolves.toBeUndefined();
    const { init } = lastCall(fetchImpl);
    expect(init.method).toBe("DELETE");
    expect(init.headers.get("If-Match")).toBe('"4"');
  });

  it("sends Idempotency-Key for postal imports", async () => {
    const { api, fetchImpl } = client(json(201, { id: "i1", status: "COMPLETED" }));
    await api.importPostalCodes("zone", [{ postal_code: "10001" }], "postal-import-abc12345");
    const { init } = lastCall(fetchImpl);
    expect(init.headers.get("Idempotency-Key")).toBe("postal-import-abc12345");
    expect(JSON.parse(String(init.body))).toEqual({ service_area_id: "zone", rows: [{ postal_code: "10001" }] });
  });

  it("targets the provider decision endpoints", async () => {
    const { api, fetchImpl } = client(json(200, { id: "a1" }));
    await api.decideApplication("a1", "request-information", "Need insurance");
    expect(lastCall(fetchImpl).url).toMatch(/\/admin\/provider-applications\/a1\/request-information$/);
  });

  it("throws ApiError on failure so screens can show the server message", async () => {
    const { api } = client(() => json(404, { detail: "Not Found" }));
    await expect(api.approvePayoutBatch("b1")).rejects.toMatchObject({ status: 404, message: "Not Found" });
  });
});
