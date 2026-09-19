import { describe, expect, it, vi } from "vitest";
import { ApiError } from "./errors";
import { ApiTransport } from "./transport";

const json = (body: unknown, init: ResponseInit = {}) => new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json", ...init.headers }, ...init });

describe("ApiTransport", () => {
  it("waits for retry backoff and clears timers after a successful read", async () => {
    vi.useFakeTimers();
    const attempts: number[] = [];
    try {
      const started = Date.now();
      const transport = new ApiTransport({
        baseUrl: "https://api.example.test",
        fetch: async () => {
          attempts.push(Date.now() - started);
          return attempts.length === 1
            ? json({ detail: "Temporarily unavailable" }, { status: 503 })
            : json({ services: ["cleaning"] });
        },
      });
      const request = transport.request("services");
      await vi.advanceTimersByTimeAsync(149);
      expect(attempts).toEqual([0]);
      await vi.advanceTimersByTimeAsync(1);
      await expect(request).resolves.toEqual({ services: ["cleaning"] });
      expect(attempts).toEqual([0, 150]);
      expect(vi.getTimerCount()).toBe(0);
    } finally {
      vi.useRealTimers();
    }
  });
  it("binds the native global fetch implementation to its global receiver", async () => {
    const originalFetch = globalThis.fetch;
    let receiver: unknown;
    globalThis.fetch = function (this: unknown) {
      receiver = this;
      return Promise.resolve(new Response(JSON.stringify({ ok: true })));
    } as typeof globalThis.fetch;
    try {
      const transport = new ApiTransport({ baseUrl: "https://api.test" });
      await transport.request("/health");
      expect(receiver).toBe(globalThis);
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it("invokes the configured fetch function without a transport receiver", async () => {
    let receiver: unknown = Symbol("unset");
    function fetcher(this: unknown) {
      receiver = this;
      return Promise.resolve(new Response(JSON.stringify({ ok: true })));
    }
    const transport = new ApiTransport({
      baseUrl: "https://api.test",
      fetch: fetcher as typeof globalThis.fetch,
    });
    await transport.request("/health");
    expect(receiver).toBeUndefined();
  });

  it("adds bearer auth and returns typed JSON", async () => {
    const fetcher = vi.fn(async (_url: URL | RequestInfo, init?: RequestInit) => {
      expect(new Headers(init?.headers).get("authorization")).toBe("Bearer token");
      return json({ ok: true });
    });
    const result = await new ApiTransport({ baseUrl: "https://api.example.test/api/v1", fetch: fetcher as typeof fetch, getAccessToken: () => "token" }).request<{ ok: boolean }>("services");
    expect(result.ok).toBe(true);
  });

  it("normalizes API domain errors and preserves request IDs", async () => {
    const fetcher = vi.fn(async () => json({ error: { code: "slot_unavailable", message: "Choose another slot" } }, { status: 409, headers: { "x-request-id": "req-7" } }));
    await expect(new ApiTransport({ baseUrl: "https://api.example.test/api/v1", fetch: fetcher as typeof fetch }).request("bookings", { method: "POST" })).rejects.toMatchObject({ kind: "conflict", code: "slot_unavailable", requestId: "req-7" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("retries safe reads but never retries writes", async () => {
    const read = vi.fn().mockResolvedValueOnce(json({}, { status: 503 })).mockResolvedValueOnce(json({ recovered: true }));
    await expect(new ApiTransport({ baseUrl: "https://api.example.test", fetch: read as typeof fetch }).request("services")).resolves.toEqual({ recovered: true });
    expect(read).toHaveBeenCalledTimes(2);
    const write = vi.fn(async () => { throw new TypeError("offline"); });
    await expect(new ApiTransport({ baseUrl: "https://api.example.test", fetch: write as typeof fetch }).request("bookings", { method: "POST", body: {} })).rejects.toBeInstanceOf(ApiError);
    expect(write).toHaveBeenCalledTimes(1);
  });

  it("reports timeouts consistently", async () => {
    const fetcher = vi.fn((_url: URL | RequestInfo, init?: RequestInit) => new Promise<Response>((_resolve, reject) => init?.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")))));
    await expect(new ApiTransport({ baseUrl: "https://api.example.test", timeoutMs: 5, fetch: fetcher as typeof fetch }).request("slow", { retry: false })).rejects.toMatchObject({ kind: "timeout" });
  });

  it("refreshes once after a 401 and retries with the rotated access token", async () => {
    let token = "expired";
    const fetcher = vi.fn(async (_url: URL | RequestInfo, init?: RequestInit) => {
      const auth = new Headers(init?.headers).get("authorization");
      return auth === "Bearer rotated" ? json({ recovered: true }) : json({ detail: "Expired" }, { status: 401 });
    });
    const refresh = vi.fn(async () => { token = "rotated"; return token; });
    const transport = new ApiTransport({ baseUrl: "https://api.example.test", fetch: fetcher as typeof fetch, getAccessToken: () => token, refreshAccessToken: refresh });
    await expect(transport.request("auth/me")).resolves.toEqual({ recovered: true });
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("ends the session without a retry loop when refresh fails", async () => {
    const expired = vi.fn(async () => json({ detail: "Expired" }, { status: 401 }));
    const unauthorized = vi.fn();
    const transport = new ApiTransport({ baseUrl: "https://api.example.test", fetch: expired as typeof fetch, refreshAccessToken: async () => null, onUnauthorized: unauthorized });
    await expect(transport.request("auth/me")).rejects.toMatchObject({ kind: "authentication" });
    expect(expired).toHaveBeenCalledTimes(1);
    expect(unauthorized).toHaveBeenCalledTimes(1);
  });
});
