"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Badge,
  Button,
  Card,
  Drawer,
  EmptyState,
  ErrorState,
  FormField,
  LoadingState,
  SearchInput,
  Select,
  ShieldIcon,
} from "@breero/ui";
import type { Department, PortalContext } from "@breero/types";
import { useApiResource } from "@/lib/customer/use-api-resource";
import {
  canAccessDepartment,
  loadPortalContext,
  resolveUnauthorizedPortalDestination,
} from "@/lib/portal";
import {
  evaluateDashboardModules,
  filterDashboardModules,
  moduleStateLabel,
  type DashboardModuleDefinition,
  type EvaluatedDashboardModule,
  type ModuleStatusFilter,
} from "./dashboard-model";
import styles from "./portal-dashboard.module.css";

export type WorkspaceModule = DashboardModuleDefinition;

export interface DepartmentDashboardProps {
  department: Department | Department[];
  eyebrow: string;
  title: string;
  description: string;
  modules: WorkspaceModule[];
}

const FILTER_OPTIONS: Array<{ value: ModuleStatusFilter; label: string }> = [
  { value: "all", label: "All modules" },
  { value: "available", label: "Available to me" },
  { value: "restricted", label: "Permission required" },
  { value: "linked", label: "Ready to open" },
  { value: "overview", label: "Overview only" },
];

export function DepartmentDashboard({
  department,
  eyebrow,
  title,
  description,
  modules,
}: DepartmentDashboardProps) {
  const load = useCallback((signal: AbortSignal): Promise<PortalContext> => loadPortalContext(signal), []);
  const { value: context, error, retry } = useApiResource(load);
  const allowedDepartments = useMemo<Department[]>(
    () => (Array.isArray(department) ? department : [department]),
    [department],
  );
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<ModuleStatusFilter>("all");
  const [selectedModule, setSelectedModule] = useState<EvaluatedDashboardModule<WorkspaceModule> | null>(null);
  const authorized = context
    ? allowedDepartments.some((item) => canAccessDepartment(context, item))
    : false;

  useEffect(() => {
    if (context && !allowedDepartments.some((item) => canAccessDepartment(context, item))) {
      const destination = resolveUnauthorizedPortalDestination(
        context.dashboard_path,
        window.location.pathname,
      );
      if (destination !== window.location.pathname) {
        window.location.replace(destination);
      }
    }
  }, [context, allowedDepartments]);

  const evaluatedModules = useMemo(
    () => (context ? evaluateDashboardModules(modules, context) : []),
    [context, modules],
  );
  const filteredModules = useMemo(
    () => filterDashboardModules(evaluatedModules, query, filter),
    [evaluatedModules, query, filter],
  );
  const availableCount = evaluatedModules.filter((item) => item.allowed).length;

  if (error) {
    return (
      <div className="shell market-section">
        <ErrorState
          title="We couldn’t load your workspace"
          description={error.message}
          onRetry={retry}
        />
      </div>
    );
  }
  if (!context) {
    return (
      <div className="shell market-section">
        <LoadingState label="Loading your authorized workspace" />
      </div>
    );
  }
  if (!authorized) {
    return (
      <div className="shell market-section">
        <LoadingState label="Routing to your authorized workspace" />
      </div>
    );
  }

  const resetDiscovery = () => {
    setQuery("");
    setFilter("all");
  };

  return (
    <div className="marketplace-page">
      <section className="shell market-section">
        <p className="market-eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p>{description}</p>
        <div className="hero-panel">
          <p>
            <ShieldIcon size={18} /> Signed in as <strong>{context.user.full_name}</strong>
          </p>
          <p>
            {context.departments.join(" · ")} · {context.identity_mode === "keycloak" ? "Secure SSO" : "Local development identity"}
          </p>
        </div>
      </section>

      <section className="shell market-section" aria-labelledby="workspace-modules-title">
        <div className="section-heading">
          <div>
            <p className="market-eyebrow">Authorized modules</p>
            <h2 id="workspace-modules-title">Your workspace</h2>
          </div>
          <Badge variant="brand">{availableCount} available</Badge>
        </div>

        <div className={styles.toolbar} aria-label="Module discovery controls">
          <FormField label="Search modules" htmlFor="dashboard-module-search" hint="Search by module, purpose, or permission identifier.">
            <SearchInput
              id="dashboard-module-search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onClear={() => setQuery("")}
              placeholder="Search this workspace"
            />
          </FormField>
          <FormField label="Filter modules" htmlFor="dashboard-module-filter">
            <Select
              id="dashboard-module-filter"
              value={filter}
              onChange={(event) => setFilter(event.target.value as ModuleStatusFilter)}
            >
              {FILTER_OPTIONS.map((option) => (
                <option value={option.value} key={option.value}>{option.label}</option>
              ))}
            </Select>
          </FormField>
        </div>

        <div className={styles.summary} aria-live="polite">
          <span>{filteredModules.length} of {evaluatedModules.length} modules shown</span>
          {(query || filter !== "all") && (
            <Button variant="ghost" size="sm" onClick={resetDiscovery}>Reset search and filters</Button>
          )}
        </div>

        {evaluatedModules.length === 0 ? (
          <EmptyState
            title="No modules documented"
            description="This department has no dashboard modules configured yet."
          />
        ) : filteredModules.length === 0 ? (
          <EmptyState
            title="No modules match"
            description="Change the search phrase or state filter to see other authorized modules."
            action={<Button variant="outline" onClick={resetDiscovery}>Show all modules</Button>}
          />
        ) : (
          <div className={styles.moduleGrid}>
            {filteredModules.map((entry) => {
              const stateLabel = moduleStateLabel(entry);
              return (
                <Card
                  interactive
                  className={styles.moduleCard}
                  key={entry.module.permission}
                  data-module-state={entry.allowed ? entry.destination : "restricted"}
                >
                  <div className={styles.moduleHeader}>
                    <Badge variant={entry.allowed ? "success" : "warning"}>{stateLabel}</Badge>
                    <span className={styles.permission}>{entry.module.permission}</span>
                  </div>
                  <h3>{entry.module.title}</h3>
                  <p>{entry.module.description}</p>
                  <div className={styles.moduleActions}>
                    <Button
                      variant="outline"
                      size="sm"
                      aria-label={`View ${entry.module.title} details`}
                      onClick={() => setSelectedModule(entry)}
                    >
                      View details
                    </Button>
                    {entry.allowed && entry.module.href ? (
                      <Link
                        className={`br-button br-button--primary br-button--sm ${styles.linkButton}`}
                        href={entry.module.href}
                      >
                        Open module
                      </Link>
                    ) : (
                      <Button size="sm" disabled>
                        {entry.allowed ? "Overview only" : "Access required"}
                      </Button>
                    )}
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </section>

      <Drawer
        open={selectedModule !== null}
        onOpenChange={(open) => { if (!open) setSelectedModule(null); }}
        title={selectedModule?.module.title ?? "Module details"}
        description={selectedModule?.module.description}
        footer={(
          <div className={styles.drawerFooter}>
            <Button variant="outline" onClick={() => setSelectedModule(null)}>Done</Button>
            {selectedModule?.allowed && selectedModule.module.href && (
              <Link
                className={`br-button br-button--primary br-button--md ${styles.linkButton}`}
                href={selectedModule.module.href}
              >
                Open module
              </Link>
            )}
          </div>
        )}
      >
        {selectedModule && (
          <div className={styles.drawerDetails}>
            <Badge variant={selectedModule.allowed ? "success" : "warning"}>
              {moduleStateLabel(selectedModule)}
            </Badge>
            <dl>
              <dt>Required permission</dt>
              <dd><code>{selectedModule.module.permission}</code></dd>
              <dt>Access decision</dt>
              <dd>{selectedModule.allowed ? "Granted by the current portal context" : "Not present in the current effective permission set"}</dd>
              <dt>Dashboard action</dt>
              <dd>{selectedModule.module.href ? "A documented screen is linked" : "No separate API-backed screen is documented in this dashboard branch"}</dd>
            </dl>
            {!selectedModule.allowed && (
              <p>Ask an authorized administrator to review your BREERO department assignment. The dashboard does not bypass backend authorization.</p>
            )}
            {selectedModule.allowed && !selectedModule.module.href && (
              <p>Your permission is active. This overview intentionally avoids inventing records, counts, or actions until a dedicated API-backed screen is implemented.</p>
            )}
          </div>
        )}
      </Drawer>
    </div>
  );
}
