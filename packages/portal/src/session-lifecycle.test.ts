import { createCipheriv, createHash, randomBytes } from "node:crypto";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { handlePortalAuthGet, handlePortalAuthPost, readLimitedBody } from "./server";
import type { PortalRuntimeConfig } from "./types";

const secret = "synthetic-portal-lifecycle-secret-32-bytes";
const csrf = "stable-synthetic-csrf";
const origin = "http://localhost:3000";
const config: PortalRuntimeConfig = { kind: "admin", title: "Admin", eyebrow: "Admin", allowedRoles: ["admin"], apiRules: [] };
const user = { id: "user", email: "admin@example.test", full_name: "Admin", role: "admin", is_active: true, email_verified: true };

function cookie(value: unknown): string {
  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", createHash("sha256").update(secret).digest(), iv);
  cipher.setAAD(Buffer.from("breero-portal:v1"));
  const encrypted = Buffer.concat([cipher.update(JSON.stringify(value)), cipher.final()]);
  return `v1.${iv.toString("base64url")}.${cipher.getAuthTag().toString("base64url")}.${encrypted.toString("base64url")}`;
}
function sessionCookies(expiring = false): string {
  const now = Math.floor(Date.now() / 1000);
  return [
    `breero-portal-access=${cookie({ v: 1, token: "test-access", expiresAt: now + (expiring ? 1 : 3600) })}`,
    `breero-portal-refresh=${cookie({ v: 1, token: "test-refresh", expiresAt: now + 7200 })}`,
    `breero-portal-profile=${cookie({ v: 1, csrfToken: csrf })}`,
  ].join("; ");
}

beforeEach(() => {
  vi.stubEnv("NODE_ENV", "test");
  vi.stubEnv("PORTAL_PUBLIC_ORIGIN", origin);
  vi.stubEnv("KEYCLOAK_ISSUER", "http://localhost:8080/realms/test");
  vi.stubEnv("KEYCLOAK_CLIENT_ID", "portal");
  vi.stubEnv("BREERO_API_INTERNAL_URL", "http://api/api/v1");
  vi.stubEnv("PORTAL_SESSION_SECRET", secret);
});
afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

describe("portal lifecycle boundaries", () => {
  it("clears local cookies with an expiring access token during an identity outage", async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error("identity unavailable"));
    vi.stubGlobal("fetch", fetcher);
    const response = await handlePortalAuthPost(new Request(`${origin}/api/auth/logout`, { method: "POST", headers: { cookie: sessionCookies(true), origin, "x-csrf-token": csrf } }), "logout", config);
    expect(response.status).toBe(200);
    expect(response.headers.getSetCookie().filter((value) => value.includes("Max-Age=0"))).toHaveLength(4);
    expect(fetcher.mock.calls.every(([url]) => !String(url).includes("/token"))).toBe(true);
  });

  it("preserves CSRF across concurrent profile reads with 32 assignments", async () => {
    const context = { user, roles: ["admin"], permissions: Array.from({ length: 80 }, (_, i) => `permission.${i}`), assignments: Array.from({ length: 32 }, (_, i) => ({ role: "admin", department: `department-${i}`, tenant_scope: "brand", vendor_id: `vendor-${i}`, is_primary: i === 0 })) };
    vi.stubGlobal("fetch", vi.fn(async (input: URL) => Response.json(String(input).endsWith("/auth/me") ? user : String(input).endsWith("/auth/access/me") ? context : {})));
    const request = () => new Request(`${origin}/api/auth/session`, { headers: { cookie: sessionCookies() } });
    const responses = await Promise.all([handlePortalAuthGet(request(), "session", config), handlePortalAuthGet(request(), "session", config)]);
    for (const response of responses) {
      expect(response.status).toBe(200);
      const body = await response.json();
      expect(body.csrf_token).toBe(csrf);
      expect(body.context.assignments).toHaveLength(32);
    }
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
