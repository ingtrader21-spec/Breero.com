import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiTransport } from "./transport";

afterEach(() => vi.unstubAllGlobals());
describe("cross-origin browser CSRF", () => {
  it.each([null, "synthetic-bearer"])("uses the API-host token with stale frontend cookie and bearer %s", async (bearer) => {
    vi.stubGlobal("document", { cookie: "breero_csrf=stale-frontend-token" });
    vi.stubGlobal("window", { location: { origin: "https://breero.com" } });
    const fetcher = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ csrf_token: "api-host-token" })))
      .mockResolvedValueOnce(new Response("{}"));
    const transport = new ApiTransport({ baseUrl: "https://api.breero.com/api/v1", fetch: fetcher, getAccessToken: () => bearer });
    await transport.request("/auth/browser/logout", { method: "POST" });
    expect(fetcher.mock.calls[0][0]).toBe("https://api.breero.com/api/v1/auth/csrf");
    expect(fetcher.mock.calls[0][1].credentials).toBe("include");
    expect(new Headers(fetcher.mock.calls[1][1].headers).get("X-CSRF-Token")).toBe("api-host-token");
  });
  it("allows a guest mutation after the channel reports no browser session", async () => {
    vi.stubGlobal("document", { cookie: "" });
    vi.stubGlobal("window", { location: { origin: "https://breero.com" } });
    const fetcher = vi.fn().mockResolvedValueOnce(new Response("{}", { status: 401 })).mockResolvedValueOnce(new Response("{}"));
    await new ApiTransport({ baseUrl: "https://api.breero.com/api/v1", fetch: fetcher }).request("/public/contact", { method: "POST" });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
  it("stops before mutation when token retrieval is forbidden", async () => {
    vi.stubGlobal("document", { cookie: "" });
    vi.stubGlobal("window", { location: { origin: "https://breero.com" } });
    const fetcher = vi.fn().mockResolvedValue(new Response("{}", { status: 403 }));
    await expect(new ApiTransport({ baseUrl: "https://api.breero.com/api/v1", fetch: fetcher }).request("/jobs", { method: "POST" })).rejects.toThrow();
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
