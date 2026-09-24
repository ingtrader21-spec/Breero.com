import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { handlePortalAuthGet, handlePortalAuthPost, proxyPortalApi, resetPortalRuntimeForTests } from "./server";
import { MemoryPortalSessionStore } from "./session-store";
import {
  adminConfig,
  apiBase,
  clientId,
  cookieValue,
  identityProvider,
  issuer,
  origin,
  partnerConfig,
  setCookies,
  type IdentityProvider,
} from "./test-harness";
import type { PortalRuntimeConfig } from "./types";

const SESSION = "breero-portal-session";
let idp: IdentityProvider;
let store: MemoryPortalSessionStore;

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2026-09-23T12:00:00Z"));
  vi.stubEnv("NODE_ENV", "test");
  vi.stubEnv("PORTAL_PUBLIC_ORIGIN", origin);
  vi.stubEnv("KEYCLOAK_ISSUER", issuer);
  vi.stubEnv("KEYCLOAK_CLIENT_ID", clientId);
  vi.stubEnv("BREERO_API_INTERNAL_URL", apiBase);
  vi.stubEnv("PORTAL_SESSION_SECRET", "synthetic-portal-boundary-secret-32-bytes");
  vi.spyOn(console, "error").mockImplementation(() => undefined);
  vi.spyOn(console, "warn").mockImplementation(() => undefined);
  idp = identityProvider();
  vi.stubGlobal("fetch", idp.fetcher);
  store = new MemoryPortalSessionStore();
  resetPortalRuntimeForTests(store);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

async function startLogin(config: PortalRuntimeConfig = adminConfig) {
  const response = await handlePortalAuthGet(new Request(`${origin}/api/auth/login?return_to=%2Fdashboard`), "login", config);
  const location = new URL(response.headers.get("location") ?? "");
  idp.lastChallenge = location.searchParams.get("code_challenge");
  idp.lastNonce = location.searchParams.get("nonce");
  return { response, location, oidc: cookieValue(response, "breero-portal-oidc") ?? "" };
}

async function callback(config: PortalRuntimeConfig, oidc: string, state: string, extraCookie = "") {
  const cookie = [`breero-portal-oidc=${oidc}`, extraCookie].filter(Boolean).join("; ");
  return handlePortalAuthGet(new Request(`${origin}/api/auth/callback?code=code-1&state=${encodeURIComponent(state)}`, { headers: { cookie } }), "callback", config);
}

async function login(config: PortalRuntimeConfig = adminConfig): Promise<{ id: string; csrf: string }> {
  const { location, oidc } = await startLogin(config);
  const response = await callback(config, oidc, location.searchParams.get("state") ?? "");
  const id = cookieValue(response, SESSION);
  if (!id) throw new Error(`login failed: ${response.headers.get("location")}`);
  const session = await handlePortalAuthGet(new Request(`${origin}/api/auth/session`, { headers: { cookie: `${SESSION}=${id}` } }), "session", config);
  const body = (await session.json()) as { csrf_token: string };
  return { id, csrf: body.csrf_token };
}

function sessionRequest(id: string, config: PortalRuntimeConfig = adminConfig) {
  return handlePortalAuthGet(new Request(`${origin}/api/auth/session`, { headers: { cookie: `${SESSION}=${id}` } }), "session", config);
}

function proxy(id: string, parts: string[], init: RequestInit & { headers?: Record<string, string> } = {}, config = adminConfig) {
  const path = parts.join("/");
  return proxyPortalApi(
    new Request(`${origin}/api/breero/${path}`, { ...init, headers: { cookie: `${SESSION}=${id}`, ...(init.headers ?? {}) } }),
    parts,
    config,
  );
}

function advance(seconds: number) {
  vi.setSystemTime(new Date(Date.now() + seconds * 1000));
}

describe("authorization code + PKCE + state + nonce", () => {
  it("starts an S256 PKCE authorization request with state and nonce", async () => {
    const { response, location, oidc } = await startLogin();
    expect(response.status).toBe(303);
    expect(location.origin + location.pathname).toBe(`${issuer}/protocol/openid-connect/auth`);
    expect(location.searchParams.get("response_type")).toBe("code");
    expect(location.searchParams.get("code_challenge_method")).toBe("S256");
    expect(location.searchParams.get("code_challenge")).toMatch(/^[A-Za-z0-9_-]{43}$/);
    expect(location.searchParams.get("state")?.length).toBeGreaterThanOrEqual(43);
    expect(location.searchParams.get("nonce")?.length).toBeGreaterThanOrEqual(43);
    expect(location.searchParams.get("redirect_uri")).toBe(`${origin}/api/auth/callback`);
    // The verifier is sealed server-side material; it never appears in the redirect.
    expect(location.toString()).not.toContain("code_verifier");
    expect(oidc).toMatch(/^v1\./);
  });

  it("issues only an opaque HttpOnly session cookie and keeps tokens server-side", async () => {
    const { location, oidc } = await startLogin();
    const response = await callback(adminConfig, oidc, location.searchParams.get("state") ?? "");
    expect(response.status).toBe(303);
    expect(response.headers.get("location")).toBe("/dashboard");
    const id = cookieValue(response, SESSION) ?? "";
    expect(id).toMatch(/^[A-Za-z0-9_-]{43}$/);
    const issued = setCookies(response).find((value) => value.startsWith(`${SESSION}=`)) ?? "";
    expect(issued).toContain("HttpOnly");
    expect(issued).toContain("SameSite=Lax");
    const everything = setCookies(response).join("\n");
    expect(everything).not.toMatch(/access-\d|refresh-\d|eyJ/);
    expect(idp.tokenGrants[0]?.get("code_verifier")).toBeTruthy();
    expect(store.size).toBe(1);

    const session = await sessionRequest(id);
    const text = await session.text();
    expect(session.status).toBe(200);
    expect(text).not.toMatch(/access-\d|refresh-\d|eyJ/);
  });

  it.each([
    ["state mismatch", async (state: string, oidc: string) => callback(adminConfig, oidc, `${state}x`)],
    ["missing transaction cookie", async (state: string) => callback(adminConfig, "", state)],
    ["tampered transaction cookie", async (state: string, oidc: string) => callback(adminConfig, `${oidc.slice(0, -4)}AAAA`, state)],
    ["expired transaction", async (state: string, oidc: string) => { advance(601); return callback(adminConfig, oidc, state); }],
  ])("rejects %s without creating a session", async (_name, run) => {
    const { location, oidc } = await startLogin();
    const response = await run(location.searchParams.get("state") ?? "", oidc);
    expect(response.headers.get("location")).toMatch(/^\/login\?error=/);
    expect(cookieValue(response, SESSION)).toBeNull();
    expect(store.size).toBe(0);
  });

  it.each([
    ["nonce mismatch", { nonce: "replayed-nonce" }],
    ["wrong audience", { aud: "another-client" }],
    ["wrong issuer", { iss: "http://localhost:8080/realms/evil" }],
    ["expired ID token", { exp: Math.floor(Date.parse("2026-09-23T12:00:00Z") / 1000) - 3600 }],
    ["foreign authorized party", { aud: [clientId, "other"], azp: "other" }],
  ])("rejects an ID token with %s", async (_name, overrides) => {
    idp.idTokenOverrides = overrides;
    const { location, oidc } = await startLogin();
    const response = await callback(adminConfig, oidc, location.searchParams.get("state") ?? "");
    expect(response.headers.get("location")).toMatch(/^\/login\?error=/);
    expect(store.size).toBe(0);
  });

  it("rejects an ID token signed by an untrusted key", async () => {
    idp.signWithUntrustedKey = true;
    const { location, oidc } = await startLogin();
    const response = await callback(adminConfig, oidc, location.searchParams.get("state") ?? "");
    expect(response.headers.get("location")).toMatch(/^\/login\?error=/);
    expect(store.size).toBe(0);
  });

  it("rotates any pre-login session identifier", async () => {
    const first = await login();
    const { location, oidc } = await startLogin();
    const response = await callback(adminConfig, oidc, location.searchParams.get("state") ?? "", `${SESSION}=${first.id}`);
    const second = cookieValue(response, SESSION);
    expect(second).toBeTruthy();
    expect(second).not.toBe(first.id);
    expect((await sessionRequest(first.id)).status).toBe(401);
  });
});

describe("role and portal boundaries", () => {
  it("denies sign-in to a portal whose role the account lacks", async () => {
    idp.roles = ["customer"];
    const { location, oidc } = await startLogin();
    const response = await callback(adminConfig, oidc, location.searchParams.get("state") ?? "");
    expect(response.headers.get("location")).toMatch(/^\/login\?error=/);
    expect(store.size).toBe(0);
  });

  it("destroys a session whose role was revoked mid-session", async () => {
    const { id } = await login();
    idp.roles = ["vendor_admin"];
    const response = await proxy(id, ["admin", "users"]);
    expect(response.status).toBe(401);
    expect(await store.get(id)).toBeNull();
    expect(idp.upstream).toHaveLength(0);
  });

  it("destroys a session for a deactivated account", async () => {
    const { id } = await login();
    idp.isActive = false;
    expect((await sessionRequest(id)).status).toBe(401);
    expect(await store.get(id)).toBeNull();
  });

  it("does not honour a session issued by another portal", async () => {
    idp.roles = ["vendor_admin", "admin"];
    const partner = await login(partnerConfig);
    const response = await sessionRequest(partner.id, adminConfig);
    expect(response.status).toBe(401);
    expect(await store.get(partner.id)).toBeNull();
  });
});

describe("invalid and expired sessions", () => {
  it.each([
    ["no cookie", ""],
    ["unknown identifier", `${SESSION}=${"A".repeat(43)}`],
    ["malformed identifier", `${SESSION}=../../etc`],
    ["legacy sealed token cookies only", "breero-portal-access=v1.a.b.c; breero-portal-refresh=v1.a.b.c; breero-portal-profile=v1.a.b.c"],
  ])("rejects %s and expires every portal cookie", async (_name, cookie) => {
    const response = await handlePortalAuthGet(new Request(`${origin}/api/auth/session`, { headers: cookie ? { cookie } : {} }), "session", adminConfig);
    expect(response.status).toBe(401);
    expect((await response.json()).code).toBe("SESSION_REQUIRED");
    const cleared = setCookies(response).filter((value) => value.includes("Max-Age=0")).map((value) => value.split("=")[0]);
    expect(cleared).toEqual(expect.arrayContaining([SESSION, "breero-portal-access", "breero-portal-refresh", "breero-portal-profile"]));
  });

  it("expires an idle session", async () => {
    const { id } = await login();
    advance(31 * 60);
    expect((await sessionRequest(id)).status).toBe(401);
    expect(await store.get(id)).toBeNull();
  });

  it("enforces the absolute session lifetime despite activity", async () => {
    const { id } = await login();
    for (let elapsed = 0; elapsed < 12 * 60 * 60; elapsed += 20 * 60) {
      advance(20 * 60);
      await sessionRequest(id);
    }
    expect((await sessionRequest(id)).status).toBe(401);
  });

  it("destroys the session when the identity provider rejects refresh", async () => {
    const { id } = await login();
    idp.refreshStatus = 400;
    advance(290);
    expect((await sessionRequest(id)).status).toBe(401);
    expect(await store.get(id)).toBeNull();
  });

  it("keeps the session but fails with 503 during an identity-provider outage", async () => {
    const { id } = await login();
    idp.refreshStatus = 503;
    advance(290);
    const response = await sessionRequest(id);
    expect(response.status).toBe(503);
    expect(await store.get(id)).not.toBeNull();
  });

  it("refreshes once for concurrent requests and rotates the refresh token", async () => {
    const { id } = await login();
    advance(290);
    const responses = await Promise.all([proxy(id, ["admin", "a"]), proxy(id, ["admin", "b"]), proxy(id, ["admin", "c"])]);
    expect(responses.map((response) => response.status)).toEqual([200, 200, 200]);
    const refreshGrants = idp.tokenGrants.filter((grant) => grant.get("grant_type") === "refresh_token");
    expect(refreshGrants).toHaveLength(1);
    expect(refreshGrants[0]?.get("refresh_token")).toBe("refresh-1");
    expect((await store.get(id))?.refreshToken).toBe("refresh-2");
    expect(idp.upstream.every((call) => call.headers.get("authorization") === "Bearer access-2")).toBe(true);
  });

  it("destroys the session when the API rejects the access token", async () => {
    const { id } = await login();
    idp.apiStatus = 401;
    expect((await proxy(id, ["admin", "users"])).status).toBe(401);
    expect(await store.get(id)).toBeNull();
  });
});

describe("CSRF boundary", () => {
  const mutate = (id: string, headers: Record<string, string>) => proxy(id, ["admin", "users"], { method: "POST", body: "{}", headers: { "content-type": "application/json", ...headers } });

  it.each([
    ["missing token", () => ({ origin })],
    ["wrong token", () => ({ origin, "x-csrf-token": "forged" })],
    ["cross-site origin", (csrf: string) => ({ origin: "https://evil.example", "x-csrf-token": csrf })],
    ["missing origin", (csrf: string) => ({ "x-csrf-token": csrf })],
  ])("rejects a mutation with %s", async (_name, headers) => {
    const { id, csrf } = await login();
    const response = await mutate(id, headers(csrf));
    expect(response.status).toBe(403);
    expect((await response.json()).code).toBe("INVALID_CSRF");
    expect(idp.upstream).toHaveLength(0);
  });

  it("forwards a same-origin mutation carrying the session CSRF token", async () => {
    const { id, csrf } = await login();
    const response = await mutate(id, { origin, "x-csrf-token": csrf });
    expect(response.status).toBe(200);
    expect(idp.upstream[0]?.method).toBe("POST");
  });

  it("does not let a forged logout destroy the session", async () => {
    const { id } = await login();
    const forged = await handlePortalAuthPost(new Request(`${origin}/api/auth/logout`, { method: "POST", headers: { cookie: `${SESSION}=${id}`, origin: "https://evil.example" } }), "logout", adminConfig);
    expect(forged.status).toBe(403);
    const wrongToken = await handlePortalAuthPost(new Request(`${origin}/api/auth/logout`, { method: "POST", headers: { cookie: `${SESSION}=${id}`, origin, "x-csrf-token": "forged" } }), "logout", adminConfig);
    expect(wrongToken.status).toBe(403);
    expect((await sessionRequest(id)).status).toBe(200);
  });
});

describe("path boundary", () => {
  it.each([
    ["an unlisted prefix", ["finance", "payout-batches"], "GET"],
    ["a prefix look-alike", ["administrator"], "GET"],
    ["a disallowed method", ["portal", "admin", "overview"], "POST"],
    ["an encoded parent segment", ["admin", "%2e%2e", "finance"], "GET"],
    ["an encoded slash", ["admin%2F..%2Ffinance"], "GET"],
    ["an encoded backslash", ["admin", "..%5Cfinance"], "GET"],
    ["an excessive path", ["admin", ...Array.from({ length: 12 }, () => "x")], "GET"],
  ])("denies %s before reaching the API", async (_name, parts, method) => {
    const { id, csrf } = await login();
    const response = await proxy(id, parts, { method, headers: { origin, "x-csrf-token": csrf }, body: method === "GET" ? undefined : "{}" });
    expect(response.status).toBe(403);
    expect((await response.json()).code).toBe("OPERATION_DENIED");
    expect(idp.upstream).toHaveLength(0);
  });
});

describe("tenant boundary", () => {
  it("never forwards client-supplied identity, tenant, or cookie headers", async () => {
    const { id } = await login();
    await proxy(id, ["admin", "users"], {
      headers: {
        authorization: "Bearer attacker-token",
        "x-tenant-id": "other-tenant",
        "x-vendor-id": "other-vendor",
        "x-legal-entity-id": "other-entity",
        "x-forwarded-for": "10.0.0.1",
      },
    });
    const forwarded = idp.upstream[0]?.headers;
    expect(forwarded?.get("authorization")).toBe("Bearer access-1");
    for (const name of ["x-tenant-id", "x-vendor-id", "x-legal-entity-id", "x-forwarded-for", "cookie"]) {
      expect(forwarded?.has(name)).toBe(false);
    }
  });

  it("destroys a session whose token resolves to a different account", async () => {
    const { id } = await login();
    idp.userId = "user-2";
    expect((await proxy(id, ["admin", "users"])).status).toBe(401);
    expect(await store.get(id)).toBeNull();
    expect(idp.upstream).toHaveLength(0);
  });

  it("passes API tenant/ownership denials through without widening access", async () => {
    const { id } = await login();
    idp.upstreamStatus = 403;
    const response = await proxy(id, ["admin", "vendors", "other"]);
    expect(response.status).toBe(403);
    expect(await store.get(id)).not.toBeNull();
  });
});

describe("logout", () => {
  it("destroys the server session, revokes the refresh token, and rejects replay", async () => {
    const { id, csrf } = await login();
    const response = await handlePortalAuthPost(new Request(`${origin}/api/auth/logout`, { method: "POST", headers: { cookie: `${SESSION}=${id}`, origin, "x-csrf-token": csrf } }), "logout", adminConfig);
    expect(response.status).toBe(200);
    const body = (await response.json()) as { logout_url: string };
    expect(body.logout_url).toContain(`${issuer}/protocol/openid-connect/logout`);
    expect(body.logout_url).not.toMatch(/refresh-|access-|id_token_hint/);
    expect(idp.endSessionCalls[0]?.get("refresh_token")).toBe("refresh-1");
    expect(setCookies(response).some((value) => value.startsWith(`${SESSION}=;`) && value.includes("Max-Age=0"))).toBe(true);
    expect(await store.get(id)).toBeNull();
    expect((await sessionRequest(id)).status).toBe(401);
  });
});

describe("runtime configuration", () => {
  it("fails closed on an unsupported session store", async () => {
    vi.stubEnv("PORTAL_SESSION_STORE", "cookie");
    const response = await handlePortalAuthGet(new Request(`${origin}/api/auth/login`), "login", adminConfig);
    expect(response.status).toBe(503);
  });
});
