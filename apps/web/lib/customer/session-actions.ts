"use client";

import { customerSession } from "./api";
import { keycloak } from "../keycloak";

const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api/v1").replace(/\/$/, "");

export const CUSTOMER_SESSION_EVENT = "breero:customer-session-changed";

async function csrfToken(): Promise<string | null> {
  try {
    const response = await fetch(`${apiBase}/auth/csrf`, {
      credentials: "include",
      cache: "no-store",
    });
    if (response.status === 401) return null;
    if (!response.ok) return null;
    const body = (await response.json()) as { csrf_token?: string };
    return body.csrf_token ?? null;
  } catch {
    return null;
  }
}

export async function hasCustomerSession(): Promise<boolean> {
  return (await csrfToken()) !== null;
}

export function notifyCustomerSessionChanged(): void {
  window.dispatchEvent(new Event(CUSTOMER_SESSION_EVENT));
}

export async function logoutCustomerSession(returnTo = "/"): Promise<void> {
  customerSession.clear();
  notifyCustomerSessionChanged();

  if (keycloak.enabled) {
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

  window.location.assign(returnTo);
}
