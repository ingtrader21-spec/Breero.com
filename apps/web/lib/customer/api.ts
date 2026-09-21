"use client";

import { createBreeroApi, createConfiguredApi, readPublicApiConfig, type AuthSession } from "@breero/api-client";
import { bookings, payments, profile, quotes } from "./data";
import { keycloak } from "../keycloak";

let refreshInFlight: Promise<string | null> | null = null;
const publicConfig = {
  NODE_ENV: process.env.NODE_ENV,
  NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL,
  NEXT_PUBLIC_API_MODE: process.env.NEXT_PUBLIC_API_MODE,
  NEXT_PUBLIC_API_TIMEOUT_MS: process.env.NEXT_PUBLIC_API_TIMEOUT_MS,
  NEXT_PUBLIC_E2E_ALLOW_MOCK: process.env.NEXT_PUBLIC_E2E_ALLOW_MOCK,
  NEXT_PUBLIC_DEPLOYMENT_ENV: process.env.NEXT_PUBLIC_DEPLOYMENT_ENV,
};

export const customerSession = {
  save(session: Pick<AuthSession, "access_token" | "refresh_token">) { void session; },
  clear() {},
  accessToken: () => null,
  async refresh(): Promise<string | null> {
    if (refreshInFlight) return refreshInFlight;
    refreshInFlight = (async () => {
      try {
        if (keycloak.enabled) {
          return null;
        }
        const config = readPublicApiConfig({ ...publicConfig, NEXT_PUBLIC_API_MODE: "live" });
        const api = createBreeroApi({ baseUrl: config.apiBaseUrl, timeoutMs: config.timeoutMs });
        await api.auth.refresh({ refresh_token: "cookie-session-not-readable-by-javascript" });
        return "cookie-session";
      } catch {
        customerSession.clear();
        return null;
      } finally { refreshInFlight = null; }
    })();
    return refreshInFlight;
  },
};

export const customerApi = createConfiguredApi(
  publicConfig,
  {
    getAccessToken: customerSession.accessToken,
    refreshAccessToken: customerSession.refresh,
    onUnauthorized: () => { customerSession.clear(); window.location.assign("/account/session-expired"); },
    mock: { bookings, payments, profile, quotes, latencyMs: 450 },
  },
);
