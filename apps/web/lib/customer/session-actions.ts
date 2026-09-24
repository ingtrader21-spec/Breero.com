"use client";

import { customerSession } from "./api";
import { keycloak } from "../keycloak";

const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api/v1").replace(/\/$/, "");

export const CUSTOMER_SESSION_EVENT = "breero:customer-session-changed";

async function csrfToken(): Promise<string | null> {
  const response = await fetch(`${apiBase}/auth/csrf`, {
    credentials: "include",
    cache: "no-store",
  });
  if (response.status === 401) return null;
  if (!response.ok) throw new Error("Unable to verify browser session");
  const body = (await response.json()) as { csrf_token?: string };
  if (!body.csrf_token) throw new Error("Unable to verify browser session");
  return body.csrf_token;
}

export async function hasCustomerSession(): Promise<boolean> {
  try {
    return (await csrfToken()) !== null;
  } catch {
    return false;
  }
}

export function notifyCustomerSessionChanged(): void {
  window.dispatchEvent(new Event(CUSTOMER_SESSION_EVENT));
}

function clearLocalSession(): void {
  customerSession.clear();
  notifyCustomerSessionChanged();
}

export async function logoutCustomerSession(returnTo = "/"): Promise<void> {
  if (keycloak.enabled) {
    clearLocalSession();
    await keycloak.logout();
    return;
  }

  const csrf = await csrfToken();
  if (csrf) {
    const response = await fetch(`${apiBase}/auth/browser/logout`, {
      method: "POST",
      credentials: "include",
      headers: { "X-CSRF-Token": csrf },
    });
    if (!response.ok && response.status !== 401) {
      throw new Error("Logout failed");
    }
  }

  clearLocalSession();
  window.location.assign(returnTo);
}
