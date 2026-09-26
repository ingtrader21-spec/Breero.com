import { describe, expect, it, vi } from "vitest";
import { OpsApiError, createOpsApi } from "./api";
import { DEFAULT_QUEUE_FILTERS } from "./queue-filters";

const BASE = "https://api.breero.test/api/v1";
const JOB = "0b7c6f1e-2a3d-4e5f-8a9b-0c1d2e3f4a5b";

type Call = { url: string; method: string; headers: Headers; body?: unknown };

function recorder(respond: (call: Call) => Response) {
  const calls: Call[] = [];
  const fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const call: Call = {
      url: String(input),
      method: init?.method ?? "GET",
      headers: new Headers(init?.headers),
      body: typeof init?.body === "string" ? JSON.parse(init.body) : undefined,
    };
    calls.push(call);
    return respond(call);
  });
  return { calls, fetch: fetch as unknown as typeof globalThis.fetch };
}

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("ops api client", () => {
  it("reads control-center projections with bearer auth and no caching", async () => {
    const { calls, fetch } = recorder(() => json({ generated_at: "2026-09-25T12:00:00Z" }));
    const api = createOpsApi({ baseUrl: BASE, token: "token-1", fetch });
    await api.dashboard();
    await api.queue({ ...DEFAULT_QUEUE_FILTERS, statuses: ["CREATED"] });
    await api.exceptions("CRITICAL");
    await api.capacity("2026-09-25", true);
    await api.serviceAreas();
    await api.integrationFailures();
    await api.jobDetail(JOB);
    await api.candidates(JOB);
    expect(calls.map((call) => call.url.replace(BASE, ""))).toEqual([
      "/operations/control-center/summary",
      "/operations/control-center/queue?status=CREATED&limit=50&offset=0",
      "/operations/control-center/exceptions?severity=CRITICAL",
      "/operations/control-center/capacity?date=2026-09-25&include_inactive=true",
      "/operations/control-center/service-areas",
      "/operations/control-center/integration-failures",
      `/operations/control-center/jobs/${JOB}`,
      `/operations/control-center/jobs/${JOB}/candidates`,
    ]);
    for (const call of calls) {
      expect(call.method).toBe("GET");
      expect(call.headers.get("Authorization")).toBe("Bearer token-1");
      expect(call.headers.has("Content-Type")).toBe(false);
    }
  });

  it("sends mutations to the canonical command endpoints", async () => {
    const { calls, fetch } = recorder(() => json({}));
    const api = createOpsApi({ baseUrl: BASE, token: "t", fetch });
    await api.match(JOB);
    await api.assign(JOB, { vendor_id: "v", worker_id: "w", reason: "closest" });
    await api.reassign(JOB, { vendor_id: "v", worker_id: "w2", reason: "rebalance", expected_version: 4 });
    await api.transition(JOB, "EN_ROUTE", "dispatched by phone");
    await api.reviewWorkRequest("wr-1", false);
    expect(calls.map((call) => [call.method, call.url.replace(BASE, ""), call.body])).toEqual([
      ["POST", `/operations/jobs/${JOB}/match`, undefined],
      ["POST", `/operations/jobs/${JOB}/assign`, { vendor_id: "v", worker_id: "w", reason: "closest" }],
      ["POST", `/operations/jobs/${JOB}/reassign`, { vendor_id: "v", worker_id: "w2", reason: "rebalance", expected_version: 4 }],
      ["POST", `/jobs/${JOB}/transition`, { status: "EN_ROUTE", reason: "dispatched by phone" }],
      ["POST", "/jobs/work-requests/wr-1/review", { approve: false }],
    ]);
    expect(calls[1].headers.get("Content-Type")).toBe("application/json");
  });

  it("encodes path identifiers", async () => {
    const { calls, fetch } = recorder(() => json({}));
    await createOpsApi({ baseUrl: BASE, fetch }).jobDetail("../admin");
    expect(calls[0].url).toBe(`${BASE}/operations/control-center/jobs/..%2Fadmin`);
  });

  it.each([
    [json({ detail: "Job has changed since it was reviewed; reload and retry" }, 409), "Job has changed since it was reviewed; reload and retry", undefined],
    [json({ error: { code: "PROVIDER_CAPACITY_UNAVAILABLE", message: "Provider capacity is no longer available" } }, 409), "Provider capacity is no longer available", "PROVIDER_CAPACITY_UNAVAILABLE"],
    [json({ detail: [{ msg: "Field required" }, { msg: "Input should be greater than 0" }] }, 422), "Field required; Input should be greater than 0", undefined],
    [new Response("<html>", { status: 502 }), "Request failed (502)", undefined],
    [new Response("null", { status: 500 }), "Request failed (500)", undefined],
  ])("surfaces the server's error message (%#)", async (response, message, code) => {
    const { fetch } = recorder(() => response);
    const failure = await createOpsApi({ baseUrl: BASE, fetch }).reassign(JOB, { vendor_id: "v", worker_id: "w", reason: "r", expected_version: 1 }).catch((error: unknown) => error);
    expect(failure).toBeInstanceOf(OpsApiError);
    expect((failure as OpsApiError).message).toBe(message);
    expect((failure as OpsApiError).code).toBe(code);
  });

  it("signs out on 401 but not on 403", async () => {
    const onUnauthorized = vi.fn();
    const unauthorized = createOpsApi({ baseUrl: BASE, fetch: recorder(() => json({ detail: "Authentication required" }, 401)).fetch, onUnauthorized });
    await expect(unauthorized.dashboard()).rejects.toMatchObject({ status: 401 });
    const forbidden = createOpsApi({ baseUrl: BASE, fetch: recorder(() => json({ detail: "Insufficient permissions" }, 403)).fetch, onUnauthorized });
    await expect(forbidden.dashboard()).rejects.toMatchObject({ status: 403, message: "Insufficient permissions" });
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it("reports network failures without leaking internals", async () => {
    const fetch = vi.fn(async () => { throw new TypeError("getaddrinfo ENOTFOUND internal-host"); }) as unknown as typeof globalThis.fetch;
    await expect(createOpsApi({ baseUrl: BASE, fetch }).dashboard()).rejects.toMatchObject({ status: 0, message: "Unable to reach the BREERO API" });
  });

  it("rejects unreadable success bodies with a stable message", async () => {
    const { fetch } = recorder(() => new Response("<html>proxy</html>", { status: 200 }));
    await expect(createOpsApi({ baseUrl: BASE, fetch }).dashboard()).rejects.toMatchObject({ status: 200, message: "The BREERO API returned an unreadable response" });
  });
});

describe("dispatch journey through the client", () => {
  it("matches, assigns, reassigns with the reviewed version, and reads back server state", async () => {
    // Minimal stand-in for the API that enforces the same version precondition.
    const state = { status: "CREATED", version: 1, worker: null as string | null };
    const { calls, fetch } = recorder((call) => {
      const path = call.url.replace(BASE, "");
      if (path.endsWith("/match")) { state.status = "OFFERED"; state.version += 2; return json([{ id: "offer-1" }]); }
      if (path.endsWith("/assign")) { state.status = "ASSIGNED"; state.version += 1; state.worker = (call.body as { worker_id: string }).worker_id; return json({ id: "a1" }, 201); }
      if (path.endsWith("/reassign")) {
        const body = call.body as { worker_id: string; expected_version: number };
        if (body.expected_version !== state.version) return json({ detail: "Job has changed since it was reviewed; reload and retry" }, 409);
        state.version += 1; state.worker = body.worker_id;
        return json({ assignment: { id: "a2" }, released_assignment_id: "a1", job_id: JOB, job_status: state.status, job_version: state.version });
      }
      return json({ job: { status: state.status, version: state.version, worker: state.worker && { id: state.worker } } });
    });
    const api = createOpsApi({ baseUrl: BASE, token: "t", fetch });

    expect(await api.match(JOB)).toHaveLength(1);
    await api.assign(JOB, { vendor_id: "v", worker_id: "w1", reason: "closest" });
    const before = await api.jobDetail(JOB);
    expect(before.job.version).toBe(4);

    const result = await api.reassign(JOB, { vendor_id: "v", worker_id: "w2", reason: "rebalance", expected_version: before.job.version });
    expect(result.job_version).toBe(5);
    await expect(
      api.reassign(JOB, { vendor_id: "v", worker_id: "w1", reason: "stale screen", expected_version: before.job.version }),
    ).rejects.toMatchObject({ status: 409 });

    const after = await api.jobDetail(JOB);
    expect(after.job.worker?.id).toBe("w2");
    expect(calls.filter((call) => call.method === "POST")).toHaveLength(4);
  });
});
