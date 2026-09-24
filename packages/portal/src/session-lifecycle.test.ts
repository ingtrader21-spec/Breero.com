import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { handlePortalAuthPost, readLimitedBody, resetPortalRuntimeForTests } from "./server";
import { MemoryPortalSessionStore, type PortalSessionRecord } from "./session-store";
import type { PortalRuntimeConfig } from "./types";

const origin = "http://localhost:3000";
const config: PortalRuntimeConfig = { kind: "admin", title: "Admin", eyebrow: "Admin", allowedRoles: ["admin"], apiRules: [] };
const sessionId = "S".repeat(43);

function record(overrides: Partial<PortalSessionRecord> = {}): PortalSessionRecord {
  const now = Math.floor(Date.now() / 1000);
  return {
    v: 1, kind: "admin", subject: "kc-user", userId: "user", accessToken: "test-access", accessExpiresAt: now + 1,
    refreshToken: "test-refresh", refreshExpiresAt: now + 7200, csrfToken: "stable-synthetic-csrf",
    createdAt: now, lastSeenAt: now, absoluteExpiresAt: now + 3600, ...overrides,
  };
}

beforeEach(() => {
  vi.stubEnv("NODE_ENV", "test");
  vi.stubEnv("PORTAL_PUBLIC_ORIGIN", origin);
  vi.stubEnv("KEYCLOAK_ISSUER", "http://localhost:8080/realms/test");
  vi.stubEnv("KEYCLOAK_CLIENT_ID", "portal");
  vi.stubEnv("BREERO_API_INTERNAL_URL", "http://api/api/v1");
  vi.stubEnv("PORTAL_SESSION_SECRET", "synthetic-portal-lifecycle-secret-32-bytes");
});
afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

describe("portal lifecycle boundaries", () => {
  it("destroys the local session with an expiring access token during an identity outage", async () => {
    const store = new MemoryPortalSessionStore();
    resetPortalRuntimeForTests(store);
    await store.set(sessionId, record());
    const fetcher = vi.fn().mockRejectedValue(new Error("identity unavailable"));
    vi.stubGlobal("fetch", fetcher);
    const response = await handlePortalAuthPost(new Request(`${origin}/api/auth/logout`, { method: "POST", headers: { cookie: `breero-portal-session=${sessionId}`, origin, "x-csrf-token": "stable-synthetic-csrf" } }), "logout", config);
    expect(response.status).toBe(200);
    expect(response.headers.getSetCookie().filter((value) => value.includes("Max-Age=0"))).toHaveLength(5);
    expect(await store.get(sessionId)).toBeNull();
    expect(fetcher.mock.calls.every(([url]) => !String(url).includes("/token"))).toBe(true);
  });

  it("stops reading a stream at its byte budget", async () => {
    const cancel = vi.fn();
    const stream = new ReadableStream({ start(controller) { controller.enqueue(new Uint8Array(17)); }, cancel });
    const request = { body: stream } as Request;
    await expect(readLimitedBody(request, 16, 100)).rejects.toMatchObject({ status: 413 });
    expect(cancel).toHaveBeenCalledOnce();
  });

  it("cancels a stalled body at the deadline", async () => {
    const cancel = vi.fn();
    const request = { body: new ReadableStream({ cancel }) } as Request;
    await expect(readLimitedBody(request, 16, 5)).rejects.toMatchObject({ status: 408 });
    expect(cancel).toHaveBeenCalledOnce();
  });
});

describe("memory session store", () => {
  it("keys records by digest and evicts the least recently written at capacity", async () => {
    const store = new MemoryPortalSessionStore(2);
    await store.set("a".repeat(43), record({ userId: "a" }));
    await store.set("b".repeat(43), record({ userId: "b" }));
    await store.set("a".repeat(43), record({ userId: "a2" }));
    await store.set("c".repeat(43), record({ userId: "c" }));
    expect(store.size).toBe(2);
    expect(await store.get("b".repeat(43))).toBeNull();
    expect((await store.get("a".repeat(43)))?.userId).toBe("a2");
  });

  it("drops records past their absolute lifetime", async () => {
    let clock = 1_000;
    const store = new MemoryPortalSessionStore(10, () => clock);
    await store.set(sessionId, record({ absoluteExpiresAt: 1_100, refreshExpiresAt: 5_000 }));
    clock = 1_100;
    expect(await store.get(sessionId)).toBeNull();
    expect(store.size).toBe(0);
  });
});
