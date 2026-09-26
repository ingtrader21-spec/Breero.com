import { describe, expect, it, vi } from "vitest";

import { ApiError, errorFromResponse, login, PartnerApi, resolveApiBase } from "../lib/api";

const BASE = "https://api.breero.test/api/v1";

type Call = { url: string; init: RequestInit };

function recorder(responder: (call: Call) => Response = () => Response.json({ items: [], total: 0 })) {
  const calls: Call[] = [];
  const fetchImpl = async (url: string, init: RequestInit = {}) => {
    const call = { url, init };
    calls.push(call);
    return responder(call);
  };
  return { calls, fetchImpl };
}

const header = (call: Call, name: string) => new Headers(call.init.headers).get(name);

describe("resolveApiBase", () => {
  it("requires an https origin and strips trailing slashes", () => {
    expect(resolveApiBase("https://api.breero.com/api/v1/")).toBe("https://api.breero.com/api/v1");
    expect(() => resolveApiBase(undefined)).toThrow();
    expect(() => resolveApiBase("http://api.breero.com/api/v1")).toThrow();
    expect(() => resolveApiBase("javascript:alert(1)")).toThrow();
  });
});

describe("PartnerApi transport", () => {
  it("authenticates with the bearer token and never sends a vendor identifier", async () => {
    const { calls, fetchImpl } = recorder();
    const api = new PartnerApi(BASE, "token-1", { fetchImpl });
    await api.workers();
    await api.addRule({ weekday: 0, start_time: "08:00", end_time: "12:00", timezone: "America/Chicago" });
    await api.jobs();
    await api.offers("PENDING");
    await api.decideOffer("offer-1", true, "worker-1");

    expect(calls.map((call) => call.url)).toEqual([
      `${BASE}/provider/workers`,
      `${BASE}/provider/availability/rules`,
      `${BASE}/provider/jobs`,
      `${BASE}/provider/offers?status=PENDING`,
      `${BASE}/provider/offers/offer-1/decision`,
    ]);
    for (const call of calls) {
      expect(header(call, "Authorization")).toBe("Bearer token-1");
      expect(call.url).not.toMatch(/vendor/i);
      expect(String(call.init.body ?? "")).not.toMatch(/vendor/i);
      expect(call.init.cache).toBe("no-store");
    }
    expect(JSON.parse(String(calls[4].init.body))).toEqual({ accept: true, worker_id: "worker-1" });
  });

  it("sends If-Match with the loaded version on versioned mutations", async () => {
    const { calls, fetchImpl } = recorder(() => new Response(null, { status: 204 }));
    const api = new PartnerApi(BASE, "t", { fetchImpl });
    await expect(api.deleteRule("rule-1", 3)).resolves.toBeUndefined();
    await api.submitQualification("q-1", 7);
    await api.saveOnboarding({ capacity: { daily_jobs: 2 } }, 12);
    await api.removeService("ps-1", 2);
    expect(calls.map((call) => [call.init.method, header(call, "If-Match")])).toEqual([
      ["DELETE", '"3"'],
      ["POST", '"7"'],
      ["PATCH", '"12"'],
      ["DELETE", '"2"'],
    ]);
  });

  it("encodes path segments", async () => {
    const { calls, fetchImpl } = recorder();
    await new PartnerApi(BASE, "t", { fetchImpl }).updateQualification("../../admin", { title: "x" }, 1);
    expect(calls[0].url).toBe(`${BASE}/provider/qualifications/..%2F..%2Fadmin`);
  });

  it("signals an expired session on 401", async () => {
    const onUnauthorized = vi.fn();
    const { fetchImpl } = recorder(() => Response.json({ detail: "Authentication required" }, { status: 401 }));
    await expect(new PartnerApi(BASE, "t", { fetchImpl, onUnauthorized }).profile()).rejects.toBeInstanceOf(ApiError);
    expect(onUnauthorized).toHaveBeenCalledOnce();
  });
});

describe("errorFromResponse", () => {
  it("maps domain errors and version conflicts", async () => {
    const error = await errorFromResponse(
      Response.json({ error: { code: "VERSION_CONFLICT", message: "Availability rule changed since it was loaded." } }, { status: 409 }),
    );
    expect(error.code).toBe("VERSION_CONFLICT");
    expect(error.isVersionConflict).toBe(true);
    expect(error.message).toContain("changed");
  });

  it("maps onboarding completeness failures", async () => {
    const error = await errorFromResponse(
      Response.json({ detail: { code: "ONBOARDING_INCOMPLETE", missing: ["services", "insurance"] } }, { status: 422 }),
    );
    expect(error.code).toBe("ONBOARDING_INCOMPLETE");
    expect(error.details).toEqual(["services", "insurance"]);
  });

  it("maps request validation errors", async () => {
    const error = await errorFromResponse(
      Response.json({ detail: [{ loc: ["body", "timezone"], msg: "Value error, timezone is not a known IANA timezone" }] }, { status: 422 }),
    );
    expect(error.code).toBe("VALIDATION_ERROR");
    expect(error.details).toEqual(["timezone: Value error, timezone is not a known IANA timezone"]);
  });

  it("maps plain HTTP errors and unreadable bodies", async () => {
    expect((await errorFromResponse(Response.json({ detail: "Offer is no longer pending" }, { status: 409 }))).message).toBe(
      "Offer is no longer pending",
    );
    expect((await errorFromResponse(new Response("<html>", { status: 502 }))).message).toBe("Request failed (502)");
  });
});

describe("login", () => {
  it("posts credentials without storing them", async () => {
    const { calls, fetchImpl } = recorder(() => Response.json({ access_token: "a", user: { email: "p@x.test", full_name: "P", role: "vendor_admin" } }));
    const session = await login(BASE, "p@x.test", "secret-password", fetchImpl);
    expect(session.access_token).toBe("a");
    expect(calls[0].url).toBe(`${BASE}/auth/login`);
    expect(calls[0].init.method).toBe("POST");
  });
});
