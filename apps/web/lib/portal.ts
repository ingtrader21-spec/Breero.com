"use client";

import type { Department, PortalContext } from "@breero/types";
import { customerApi } from "./customer/api";

const ALLOWED_DASHBOARDS = new Set([
  "/account", "/provider", "/worker", "/ops", "/support", "/finance",
  "/quality", "/trust-safety", "/sales", "/marketing", "/admin",
]);

export async function loadPortalContext(signal?: AbortSignal): Promise<PortalContext> {
  const context = await customerApi.auth.context(signal);
  if (!ALLOWED_DASHBOARDS.has(context.dashboard_path)) throw new Error("Account dashboard is not configured");
  return context;
}

export async function routeToPortal(): Promise<void> {
  const context = await loadPortalContext();
  window.location.replace(context.dashboard_path);
}

export function canAccessDepartment(context: PortalContext, department: Department): boolean {
  return context.departments.includes(department);
}
