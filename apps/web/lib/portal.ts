"use client";

import type { Department, PortalContext } from "@breero/types";
import { customerApi } from "./customer/api";

export const ACCESS_DENIED_DASHBOARD = "/access-denied";

const ALLOWED_DASHBOARDS = new Set([
  "/account",
  "/provider",
  "/worker",
  "/ops",
  "/support",
  "/finance",
  "/quality",
  "/trust-safety",
  "/sales",
  "/marketing",
  "/admin",
  ACCESS_DENIED_DASHBOARD,
]);

export function assertAllowedDashboard(dashboardPath: string): void {
  if (!ALLOWED_DASHBOARDS.has(dashboardPath)) {
    throw new Error("Account dashboard is not configured");
  }
}

export function resolveUnauthorizedPortalDestination(
  dashboardPath: string,
  currentPath: string,
): string {
  assertAllowedDashboard(dashboardPath);
  return dashboardPath === currentPath ? ACCESS_DENIED_DASHBOARD : dashboardPath;
}

export async function loadPortalContext(signal?: AbortSignal): Promise<PortalContext> {
  const context = await customerApi.auth.context(signal);
  assertAllowedDashboard(context.dashboard_path);
  return context;
}

export async function routeToPortal(returnTo?: string): Promise<void> {
  const context = await loadPortalContext();
  let destination = resolveUnauthorizedPortalDestination(
    context.dashboard_path,
    window.location.pathname,
  );
  if (returnTo && context.dashboard_path !== ACCESS_DENIED_DASHBOARD) {
    try {
      const requested = new URL(returnTo, window.location.origin);
      // A return path may resume work only inside the backend-assigned workspace.
      if (
        requested.origin === window.location.origin &&
        (requested.pathname === context.dashboard_path ||
          requested.pathname.startsWith(`${context.dashboard_path}/`))
      ) {
        destination = `${requested.pathname}${requested.search}${requested.hash}`;
      }
    } catch {
      // An invalid return path falls back to the authorized dashboard.
    }
  }
  if (destination !== window.location.pathname) {
    window.location.replace(destination);
  }
}

export function canAccessDepartment(context: PortalContext, department: Department): boolean {
  return context.departments.includes(department);
}
