import { describe, expect, it, vi } from "vitest";
import { createBreeroApi } from "./client";
import { createConfiguredApi } from "./factory";
import { readPublicApiConfig } from "./config";

const userId = "123e4567-e89b-42d3-a456-426614174000";
const portalContext = {
  user: {
    id: userId,
    email: "support@breero.test",
    full_name: "Support User",
    role: "operations",
    is_active: true,
    email_verified: true,
  },
  brand_key: "breero",
  dashboard_path: "/support",
  roles: ["support"],
  departments: ["customer_support"],
  permissions: ["support.customers.read"],
  assignments: [],
  identity_mode: "keycloak",
};

describe("BREERO client", () => {
  it("sends idempotency keys on booking writes", async () => {
    const fetcher = vi.fn(async (_url: URL | RequestInfo, init?: RequestInit) => {
      expect(new Headers(init?.headers).get("idempotency-key")).toBe("booking-123456");
      return new Response(JSON.stringify({ id: "b" }), { status: 201 });
    });
    const api = createBreeroApi({ baseUrl: "https://api.test/api/v1", fetch: fetcher as typeof fetch });
    await api.bookings.create({ service_id: "s", address_id: "a", customer: { first_name: "A", last_name: "B", email: "a@b.test", phone: "12345" }, window: { start: "start", end: "end" }, answers: [] }, "booking-123456");
  });

  it("requests the configured login mode", async () => {
    const fetcher = vi.fn(async (url: URL | RequestInfo, init?: RequestInit) => {
      expect(String(url)).toBe("https://api.test/api/v1/auth/login-mode");
      expect(init?.method ?? "GET").toBe("GET");
      return new Response(JSON.stringify({ mode: "keycloak", issuer: "https://auth.codestra.co/realms/codestra" }), { status: 200 });
    });
    const api = createBreeroApi({ baseUrl: "https://api.test/api/v1", fetch: fetcher as typeof fetch });

    await expect(api.auth.loginMode()).resolves.toEqual({
      mode: "keycloak",
      issuer: "https://auth.codestra.co/realms/codestra",
    });
  });

  it("requests the authenticated portal context", async () => {
    const fetcher = vi.fn(async (url: URL | RequestInfo, init?: RequestInit) => {
      expect(String(url)).toBe("https://api.test/api/v1/auth/context");
      expect(init?.method ?? "GET").toBe("GET");
      return new Response(JSON.stringify(portalContext), { status: 200 });
    });
    const api = createBreeroApi({ baseUrl: "https://api.test/api/v1", fetch: fetcher as typeof fetch });

    await expect(api.auth.context()).resolves.toMatchObject({
      dashboard_path: "/support",
      identity_mode: "keycloak",
    });
  });

  it("loads the access catalog through the documented admin endpoint", async () => {
    const fetcher = vi.fn(async (url: URL | RequestInfo, init?: RequestInit) => {
      expect(String(url)).toBe("https://api.test/api/v1/auth/access/catalog");
      expect(init?.method ?? "GET").toBe("GET");
      return new Response(JSON.stringify({
        roles: ["support", "admin"],
        departments: ["customer_support", "administration"],
        tenant_scopes: ["global", "brand", "vendor"],
      }), { status: 200 });
    });
    const api = createBreeroApi({ baseUrl: "https://api.test/api/v1", fetch: fetcher as typeof fetch });

    await expect(api.auth.accessCatalog()).resolves.toMatchObject({
      roles: ["support", "admin"],
      tenant_scopes: ["global", "brand", "vendor"],
    });
  });

  it("loads one user access profile before replacement", async () => {
    const fetcher = vi.fn(async (url: URL | RequestInfo, init?: RequestInit) => {
      expect(String(url)).toBe(`https://api.test/api/v1/auth/access/users/${userId}`);
      expect(init?.method ?? "GET").toBe("GET");
      return new Response(JSON.stringify(portalContext), { status: 200 });
    });
    const api = createBreeroApi({ baseUrl: "https://api.test/api/v1", fetch: fetcher as typeof fetch });

    await expect(api.auth.userAccess(userId)).resolves.toMatchObject({
      user: { id: userId, email: "support@breero.test" },
      dashboard_path: "/support",
    });
  });

  it("writes department access through the shared client", async () => {
    const fetcher = vi.fn(async (url: URL | RequestInfo, init?: RequestInit) => {
      expect(String(url)).toBe(`https://api.test/api/v1/auth/access/users/${userId}`);
      expect(init?.method).toBe("PUT");
      const body = JSON.parse(String(init?.body));
      expect(body.assignments[0]).toMatchObject({
        role: "support",
        department: "customer_support",
        tenant_scope: "brand",
      });
      return new Response(JSON.stringify(portalContext), { status: 200 });
    });
    const api = createBreeroApi({ baseUrl: "https://api.test/api/v1", fetch: fetcher as typeof fetch });

    await expect(api.auth.replaceUserAccess(userId, {
      assignments: [{
        role: "support",
        department: "customer_support",
        tenant_scope: "brand",
        is_primary: true,
      }],
    })).resolves.toMatchObject({ dashboard_path: "/support" });
  });

  it("switches all domains through one mock seam", async () => {
    const api = createConfiguredApi({ NEXT_PUBLIC_API_MODE: "mock" }, { mock: { services: [] } });
    await expect(api.services.list()).resolves.toEqual([]);
  });

  it("accepts the exact live staging origin in a production build", () => {
    expect(
      readPublicApiConfig({
        NODE_ENV: "production",
        NEXT_PUBLIC_DEPLOYMENT_ENV: "staging",
        NEXT_PUBLIC_API_BASE_URL: "https://api-staging.breero.com/api/v1",
        NEXT_PUBLIC_API_MODE: "live",
      }),
    ).toMatchObject({
      apiBaseUrl: "https://api-staging.breero.com/api/v1",
      mode: "live",
    });
  });

  it("rejects a production origin for a staging deployment", () => {
    expect(() =>
      readPublicApiConfig({
        NODE_ENV: "production",
        NEXT_PUBLIC_DEPLOYMENT_ENV: "staging",
        NEXT_PUBLIC_API_BASE_URL: "https://api.breero.com/api/v1",
      }),
    ).toThrow("staging requires https://api-staging.breero.com/api/v1");
  });
});
