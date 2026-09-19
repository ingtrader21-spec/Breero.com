"use client";

import { createBreeroApi, createConfiguredApi, readPublicApiConfig, type AuthSession } from "@breero/api-client";
import type { PortalContext } from "@breero/types";
import { bookings, payments, profile, quotes } from "./data";
import { keycloak } from "../keycloak";

const ACCESS_KEY = "breero_access_token";
const REFRESH_KEY = "breero_refresh_token";
let refreshInFlight: Promise<string | null> | null = null;
const publicConfig = {
  NODE_ENV: process.env.NODE_ENV,
  NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL,
  NEXT_PUBLIC_API_MODE: process.env.NEXT_PUBLIC_API_MODE,
  NEXT_PUBLIC_API_TIMEOUT_MS: process.env.NEXT_PUBLIC_API_TIMEOUT_MS,
  NEXT_PUBLIC_E2E_ALLOW_MOCK: process.env.NEXT_PUBLIC_E2E_ALLOW_MOCK,
  NEXT_PUBLIC_DEPLOYMENT_ENV: process.env.NEXT_PUBLIC_DEPLOYMENT_ENV,
};

const e2eAdminSession: AuthSession = {
  access_token: "e2e-admin-access-token",
  refresh_token: "e2e-admin-refresh-token",
  token_type: "bearer",
  expires_in: 3600,
  refresh_expires_in: 86400,
  user: {
    id: "00000000-0000-4000-8000-000000000071",
    email: "e2e-admin@breero.test",
    full_name: "BREERO E2E Administrator",
    role: "admin",
    is_active: true,
    email_verified: true,
  },
};

const e2eAdminContext: PortalContext = {
  user: e2eAdminSession.user,
  brand_key: "breero",
  dashboard_path: "/admin",
  roles: ["admin"],
  departments: ["administration"],
  permissions: [
    "admin.access.manage",
    "admin.integrations.read",
    "email.domain.read",
    "email.domain.manage",
    "email.domain.verify",
    "email.sender.read",
    "email.sender.manage",
    "email.credential.read",
    "email.credential.manage",
    "email.message.compose",
    "email.message.read",
    "email.outbox.read",
    "email.outbox.retry",
  ],
  assignments: [
    {
      role: "admin",
      department: "administration",
      tenant_scope: "global",
      vendor_id: null,
      is_primary: true,
    },
  ],
  identity_mode: "local",
};

export const customerSession = {
  save(session: Pick<AuthSession, "access_token" | "refresh_token">) {
    window.sessionStorage.setItem(ACCESS_KEY, session.access_token);
    if (session.refresh_token) window.sessionStorage.setItem(REFRESH_KEY, session.refresh_token);
  },
  clear() {
    window.sessionStorage.removeItem(ACCESS_KEY);
    window.sessionStorage.removeItem(REFRESH_KEY);
  },
  accessToken: () => typeof window === "undefined" ? null : window.sessionStorage.getItem(ACCESS_KEY),
  async refresh(): Promise<string | null> {
    if (refreshInFlight) return refreshInFlight;
    refreshInFlight = (async () => {
      const refreshToken = window.sessionStorage.getItem(REFRESH_KEY);
      if (!refreshToken) return null;
      try {
        if (keycloak.enabled) {
          const session = await keycloak.refresh(refreshToken);
          customerSession.save(session);
          return session.access_token;
        }
        const config = readPublicApiConfig({ ...publicConfig, NEXT_PUBLIC_API_MODE: "live" });
        const api = createBreeroApi({ baseUrl: config.apiBaseUrl, timeoutMs: config.timeoutMs });
        const session = await api.auth.refresh({ refresh_token: refreshToken });
        customerSession.save(session);
        return session.access_token;
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
    mock: {
      bookings,
      payments,
      profile,
      quotes,
      session: e2eAdminSession,
      portalContext: e2eAdminContext,
      loginMode: { mode: "local", issuer: "" },
      emailDomains: [],
      emailSenders: [],
      emailCredentials: [],
      emailMessages: [],
      emailOutbox: [],
      latencyMs: 100,
    },
  },
);
