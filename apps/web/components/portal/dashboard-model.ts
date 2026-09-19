import type { PortalContext } from "@breero/types";

export type ModuleStatusFilter = "all" | "available" | "restricted" | "linked" | "overview";

export interface DashboardModuleDefinition {
  title: string;
  description: string;
  permission: string;
  href?: string;
}

export interface EvaluatedDashboardModule<T extends DashboardModuleDefinition = DashboardModuleDefinition> {
  module: T;
  allowed: boolean;
  destination: "linked" | "overview";
}

export function hasModulePermission(context: PortalContext, permission: string): boolean {
  return context.permissions.includes("*") || context.permissions.includes(permission);
}

export function evaluateDashboardModules<T extends DashboardModuleDefinition>(
  modules: T[],
  context: PortalContext,
): EvaluatedDashboardModule<T>[] {
  return modules.map((module) => ({
    module,
    allowed: hasModulePermission(context, module.permission),
    destination: module.href ? "linked" : "overview",
  }));
}

export function filterDashboardModules<T extends DashboardModuleDefinition>(
  modules: EvaluatedDashboardModule<T>[],
  query: string,
  filter: ModuleStatusFilter,
): EvaluatedDashboardModule<T>[] {
  const normalizedQuery = query.trim().toLocaleLowerCase();

  return modules.filter((entry) => {
    const matchesQuery = !normalizedQuery || [
      entry.module.title,
      entry.module.description,
      entry.module.permission,
    ].some((value) => value.toLocaleLowerCase().includes(normalizedQuery));

    if (!matchesQuery) return false;
    if (filter === "available") return entry.allowed;
    if (filter === "restricted") return !entry.allowed;
    if (filter === "linked") return entry.allowed && entry.destination === "linked";
    if (filter === "overview") return entry.allowed && entry.destination === "overview";
    return true;
  });
}

export function moduleStateLabel(entry: EvaluatedDashboardModule): string {
  if (!entry.allowed) return "Permission required";
  if (entry.destination === "linked") return "Ready to open";
  return "Access enabled";
}
