"use client";

import {
  createContext,
  type ChangeEvent,
  type FormEvent,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import type {
  PortalCapabilities,
  PortalProblem,
  PortalRuntimeConfig,
  PortalSessionState,
  PortalSessionView,
} from "./types";

export type {
  PortalApiRule,
  PortalAssignment,
  PortalCapabilities,
  PortalContext,
  PortalHttpMethod,
  PortalKind,
  PortalProblem,
  PortalRuntimeConfig,
  PortalSessionView,
  PortalUser,
} from "./types";

interface PortalSessionContextValue {
  state: PortalSessionState;
  refresh: () => Promise<void>;
  request: <T>(path: string, init?: RequestInit) => Promise<T>;
  signOut: () => Promise<void>;
}

const PortalSessionContext = createContext<PortalSessionContextValue | null>(null);
const SESSION_CHANNEL = "breero-portal-session";
const CLIENT_TIMEOUT_MS = 15_000;

function isMutation(method: string | undefined): boolean {
  return !["GET", "HEAD", "OPTIONS"].includes((method ?? "GET").toUpperCase());
}

async function readProblem(response: Response): Promise<PortalProblem> {
  const fallback: PortalProblem = {
    status: response.status,
    message: `Request failed (${response.status})`,
  };
  try {
    const value = (await response.json()) as Partial<PortalProblem> & {
      detail?: unknown;
      message?: unknown;
    };
    const detail =
      typeof value.detail === "string"
        ? value.detail
        : typeof value.message === "string"
          ? value.message
          : fallback.message;
    return {
      status: response.status,
      message: detail,
      requestId:
        value.requestId ??
        response.headers.get("x-request-id") ??
        response.headers.get("x-correlation-id") ??
        undefined,
      code: value.code,
    };
  } catch {
    return fallback;
  }
}

function problemError(problem: PortalProblem): Error & { problem: PortalProblem } {
  return Object.assign(new Error(problem.message), { problem });
}

async function loadSession(): Promise<PortalSessionView | null> {
  const response = await fetch("/api/auth/session", {
    headers: { Accept: "application/json" },
    cache: "no-store",
    credentials: "same-origin",
    signal: AbortSignal.timeout(CLIENT_TIMEOUT_MS),
  });
  if (response.status === 401) return null;
  if (!response.ok) throw problemError(await readProblem(response));
  return (await response.json()) as PortalSessionView;
}

export function PortalSessionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<PortalSessionState>({ status: "loading" });

  const refresh = useCallback(async () => {
    try {
      const session = await loadSession();
      setState(session ? { status: "authenticated", session } : { status: "anonymous" });
    } catch (error) {
      setState({
        status: "anonymous",
        message: error instanceof Error ? error.message : "Portal session is unavailable",
      });
    }
  }, []);

  useEffect(() => {
    void refresh();
    const channel = typeof BroadcastChannel === "undefined" ? null : new BroadcastChannel(SESSION_CHANNEL);
    const onVisibility = () => {
      if (document.visibilityState === "visible") void refresh();
    };
    const onOnline = () => void refresh();
    channel?.addEventListener("message", refresh);
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("online", onOnline);
    return () => {
      channel?.removeEventListener("message", refresh);
      channel?.close();
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("online", onOnline);
    };
  }, [refresh]);

  const request = useCallback(
    async <T,>(path: string, init?: RequestInit): Promise<T> => {
      if (!path.startsWith("/") || path.startsWith("//")) {
        throw new Error("Portal API path must be relative");
      }
      const method = (init?.method ?? "GET").toUpperCase();
      if (isMutation(method) && typeof navigator !== "undefined" && !navigator.onLine) {
        throw new Error("You are offline. Changes are blocked until the connection returns.");
      }
      if (state.status !== "authenticated") throw new Error("Authentication required");
      const headers = new Headers(init?.headers);
      headers.set("Accept", "application/json");
      headers.set("X-CSRF-Token", state.session.csrf_token);
      if (init?.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
      const response = await fetch(`/api/breero${path}`, {
        ...init,
        method,
        headers,
        credentials: "same-origin",
        cache: "no-store",
        signal: AbortSignal.timeout(CLIENT_TIMEOUT_MS),
      });
      if (response.status === 401) {
        setState({ status: "anonymous", message: "Your session expired. Sign in again." });
        if (typeof BroadcastChannel !== "undefined") {
          const channel = new BroadcastChannel(SESSION_CHANNEL);
          channel.postMessage("expired");
          channel.close();
        }
      }
      if (!response.ok) throw problemError(await readProblem(response));
      if (response.status === 204) return undefined as T;
      const contentType = response.headers.get("content-type") ?? "";
      if (!contentType.includes("application/json")) return (await response.text()) as T;
      return (await response.json()) as T;
    },
    [state],
  );

  const signOut = useCallback(async () => {
    if (state.status !== "authenticated") {
      window.location.assign("/login");
      return;
    }
    let destination = "/login";
    try {
      const response = await fetch("/api/auth/logout", {
        method: "POST",
        headers: {
          Accept: "application/json",
          "X-CSRF-Token": state.session.csrf_token,
        },
        credentials: "same-origin",
        cache: "no-store",
        signal: AbortSignal.timeout(CLIENT_TIMEOUT_MS),
      });
      if (response.ok) {
        const body = (await response.json()) as { logout_url?: string };
        if (body.logout_url) destination = body.logout_url;
      }
    } finally {
      setState({ status: "anonymous" });
      if (typeof BroadcastChannel !== "undefined") {
        const channel = new BroadcastChannel(SESSION_CHANNEL);
        channel.postMessage("logout");
        channel.close();
      }
      window.location.assign(destination);
    }
  }, [state]);

  const value = useMemo<PortalSessionContextValue>(
    () => ({ state, refresh, request, signOut }),
    [refresh, request, signOut, state],
  );
  return <PortalSessionContext.Provider value={value}>{children}</PortalSessionContext.Provider>;
}

export function usePortalSession(): PortalSessionContextValue {
  const value = useContext<PortalSessionContextValue | null>(PortalSessionContext);
  if (!value) throw new Error("usePortalSession must be used inside PortalSessionProvider");
  return value;
}

export interface PortalNavigationItem {
  id: string;
  label: string;
  description?: string;
  badge?: string | number;
}

export function PortalLoginPage({ config }: { config: PortalRuntimeConfig }) {
  const [returnTo, setReturnTo] = useState("/");
  const [error, setError] = useState("");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const requested = params.get("return_to");
    if (requested?.startsWith("/") && !requested.startsWith("//")) setReturnTo(requested);
    setError(params.get("error") ?? "");
  }, []);

  return (
    <main className="portal-login">
      <section className="portal-login__card" aria-labelledby="portal-login-title">
        <a className="portal-wordmark portal-wordmark--dark" href="https://breero.com">
          BREERO
        </a>
        <p className="portal-eyebrow">{config.eyebrow}</p>
        <h1 id="portal-login-title">Secure access to {config.title}</h1>
        <p>
          Continue through Codestra Identity. Passwords and bearer tokens are never exposed to
          this browser application.
        </p>
        {error ? <p className="portal-error" role="alert">{error}</p> : null}
        <a
          className="portal-primary-action"
          href={`/api/auth/login?return_to=${encodeURIComponent(returnTo)}`}
        >
          Continue to secure sign in
        </a>
        <div className="portal-login__trust" aria-label="Security controls">
          <span>Authorization Code + PKCE</span>
          <span>HTTP-only session</span>
          <span>Role-scoped API</span>
        </div>
        <p className="portal-small">
          Access is restricted to provisioned BREERO team and partner accounts.
        </p>
      </section>
    </main>
  );
}

export function PortalApplication({
  config,
  navigation,
  activeId,
  onNavigate,
  children,
}: {
  config: PortalRuntimeConfig;
  navigation: readonly PortalNavigationItem[];
  activeId: string;
  onNavigate: (id: string) => void;
  children: ReactNode;
}) {
  const { state, signOut } = usePortalSession();
  if (state.status === "loading") return <PortalLoading label="Loading secure workspace" fullPage />;
  if (state.status === "anonymous") {
    return (
      <main className="portal-login">
        <section className="portal-login__card" aria-live="polite">
          <a className="portal-wordmark portal-wordmark--dark" href="https://breero.com">BREERO</a>
          <p className="portal-eyebrow">{config.eyebrow}</p>
          <h1>{config.title}</h1>
          <p>{state.message ?? "Sign in to open this secure workspace."}</p>
          <a className="portal-primary-action" href="/login">Sign in</a>
        </section>
      </main>
    );
  }
  const active = navigation.find((item) => item.id === activeId) ?? navigation[0];
  return (
    <div className="portal-shell">
      <aside className="portal-sidebar">
        <a className="portal-wordmark" href="https://breero.com" aria-label="BREERO home">BREERO</a>
        <div className="portal-identity">
          <span>{config.eyebrow}</span>
          <strong>{config.title}</strong>
        </div>
        <nav aria-label={`${config.title} navigation`}>
          {navigation.map((item) => (
            <button
              type="button"
              key={item.id}
              className={item.id === active.id ? "is-active" : ""}
              aria-current={item.id === active.id ? "page" : undefined}
              onClick={() => onNavigate(item.id)}
            >
              <span>{item.label}</span>
              {item.badge !== undefined ? <small>{item.badge}</small> : null}
            </button>
          ))}
        </nav>
        <div className="portal-sidebar__footer">
          <p>{state.session.user.full_name}</p>
          <span>{state.session.user.email}</span>
          <button type="button" onClick={() => void signOut()}>Sign out</button>
        </div>
      </aside>
      <main className="portal-main">
        <header className="portal-header">
          <div>
            <p className="portal-eyebrow">{config.eyebrow}</p>
            <h1>{active.label}</h1>
            {active.description ? <p>{active.description}</p> : null}
          </div>
          <div className="portal-header__status">
            <span className="portal-presence" aria-hidden="true" />
            Secure session
          </div>
        </header>
        {children}
      </main>
    </div>
  );
}

export function PortalFoundationPage({ config }: { config: PortalRuntimeConfig }) {
  const [activeId, setActiveId] = useState("overview");
  const navigation: PortalNavigationItem[] = [
    { id: "overview", label: "Overview", description: "Live access and capability status." },
    { id: "security", label: "Security", description: "Identity and authorization controls." },
  ];
  return (
    <PortalSessionProvider>
      <PortalApplication
        config={config}
        navigation={navigation}
        activeId={activeId}
        onNavigate={setActiveId}
      >
        <FoundationPanel activeId={activeId} />
      </PortalApplication>
    </PortalSessionProvider>
  );
}

function FoundationPanel({ activeId }: { activeId: string }) {
  const { state } = usePortalSession();
  if (state.status !== "authenticated") return null;
  if (activeId === "security") {
    return (
      <PortalSection title="Access boundary" subtitle="Effective controls for this browser session.">
        <dl className="portal-definition-grid">
          <div><dt>Identity mode</dt><dd>{state.session.context.identity_mode}</dd></div>
          <div><dt>Roles</dt><dd>{state.session.context.roles.join(", ") || "None"}</dd></div>
          <div><dt>Departments</dt><dd>{state.session.context.departments.join(", ") || "None"}</dd></div>
          <div><dt>Tenant scope</dt><dd>{state.session.context.assignments[0]?.tenant_scope ?? "None"}</dd></div>
        </dl>
        <PortalNotice tone="success" title="Browser security active">
          API bearer tokens are held inside encrypted HTTP-only session envelopes. Mutations require
          same-origin requests and a per-session CSRF token.
        </PortalNotice>
      </PortalSection>
    );
  }
  return (
    <>
      <section className="portal-metric-grid" aria-label="Portal access summary">
        <MetricCard label="Roles" value={state.session.context.roles.length} detail="Effective assignments" />
        <MetricCard label="Permissions" value={state.session.context.permissions.length} detail="Backend enforced" />
        <MetricCard label="Session" value="Active" detail="Automatic refresh" tone="success" />
        <MetricCard label="Data" value="Live" detail="No fixture records" tone="success" />
      </section>
      <PortalSection title="Effective capabilities" subtitle="These values come from the canonical BREERO API.">
        <CapabilityGrid capabilities={state.session.capabilities} />
      </PortalSection>
    </>
  );
}

export function MetricCard({
  label,
  value,
  detail,
  tone = "default",
}: {
  label: string;
  value: string | number;
  detail?: string;
  tone?: "default" | "success" | "warning" | "danger";
}) {
  return (
    <article className={`portal-metric portal-metric--${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      {detail ? <small>{detail}</small> : null}
    </article>
  );
}

export function CapabilityGrid({ capabilities }: { capabilities: PortalCapabilities }) {
  const entries = Object.entries(capabilities).filter(([, value]) => typeof value === "boolean") as [
    string,
    boolean,
  ][];
  return (
    <div className="portal-capability-grid">
      {entries.map(([key, enabled]) => (
        <div key={key}>
          <StatusBadge value={enabled ? "enabled" : "disabled"} />
          <span>{formatLabel(key)}</span>
        </div>
      ))}
    </div>
  );
}

export function PortalSection({
  title,
  subtitle,
  actions,
  children,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="portal-panel">
      <div className="portal-panel__heading">
        <div><h2>{title}</h2>{subtitle ? <p>{subtitle}</p> : null}</div>
        {actions ? <div className="portal-panel__actions">{actions}</div> : null}
      </div>
      {children}
    </section>
  );
}

export function PortalNotice({
  title,
  tone = "info",
  children,
}: {
  title: string;
  tone?: "info" | "success" | "warning" | "danger";
  children: ReactNode;
}) {
  return (
    <div className={`portal-notice portal-notice--${tone}`} role={tone === "danger" ? "alert" : "status"}>
      <strong>{title}</strong>
      <div>{children}</div>
    </div>
  );
}

export function PortalLoading({ label = "Loading", fullPage = false }: { label?: string; fullPage?: boolean }) {
  return (
    <div className={fullPage ? "portal-loading portal-loading--page" : "portal-loading"} role="status">
      <span className="portal-spinner" aria-hidden="true" />
      <span>{label}…</span>
    </div>
  );
}

export function PortalEmpty({ title, detail }: { title: string; detail?: string }) {
  return <div className="portal-empty"><strong>{title}</strong>{detail ? <p>{detail}</p> : null}</div>;
}

export function PortalError({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const problem =
    error instanceof Error && "problem" in error
      ? (error as Error & { problem: PortalProblem }).problem
      : null;
  return (
    <div className="portal-error-block" role="alert">
      <strong>Unable to load this workspace</strong>
      <p>{error instanceof Error ? error.message : "An unexpected error occurred."}</p>
      {problem?.requestId ? <small>Request ID: {problem.requestId}</small> : null}
      {onRetry ? <button type="button" onClick={onRetry}>Try again</button> : null}
    </div>
  );
}

export function StatusBadge({ value }: { value: string | boolean | null | undefined }) {
  const normalized = String(value ?? "unknown").toLowerCase();
  const positive = ["active", "approved", "available", "completed", "delivered", "enabled", "ready", "verified"];
  const negative = ["cancelled", "disabled", "expired", "failed", "rejected", "suspended", "terminal"];
  const warning = ["draft", "held", "pending", "processing", "requested", "retrying", "unverified"];
  const tone = positive.some((item) => normalized.includes(item))
    ? "success"
    : negative.some((item) => normalized.includes(item))
      ? "danger"
      : warning.some((item) => normalized.includes(item))
        ? "warning"
        : "neutral";
  return <span className={`portal-badge portal-badge--${tone}`}>{formatLabel(normalized)}</span>;
}

export interface DataColumn<T> {
  key: string;
  label: string;
  render: (row: T) => ReactNode;
  compact?: boolean;
}

export function DataTable<T>({
  rows,
  columns,
  rowKey,
  emptyTitle = "No records available",
}: {
  rows: readonly T[];
  columns: readonly DataColumn<T>[];
  rowKey: (row: T) => string;
  emptyTitle?: string;
}) {
  if (!rows.length) return <PortalEmpty title={emptyTitle} detail="No fixture or placeholder records are shown." />;
  return (
    <div className="portal-table-wrap">
      <table>
        <thead><tr>{columns.map((column) => <th key={column.key}>{column.label}</th>)}</tr></thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)}>
              {columns.map((column) => (
                <td key={column.key} className={column.compact ? "is-compact" : undefined}>{column.render(row)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function usePortalQuery<T>(path: string | null) {
  const { request } = usePortalSession();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(Boolean(path));
  const [version, setVersion] = useState(0);
  const retry = useCallback(() => setVersion((value) => value + 1), []);

  useEffect(() => {
    let active = true;
    if (!path) {
      setLoading(false);
      setData(null);
      return () => { active = false; };
    }
    setLoading(true);
    setError(null);
    void request<T>(path)
      .then((value) => { if (active) setData(value); })
      .catch((reason) => { if (active) setError(reason); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [path, request, version]);

  return { data, error, loading, retry };
}

export function PortalConfirmForm({
  title,
  description,
  confirmLabel,
  onConfirm,
  disabled = false,
}: {
  title: string;
  description: string;
  confirmLabel: string;
  onConfirm: () => Promise<void>;
  disabled?: boolean;
}) {
  const [confirmed, setConfirmed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!confirmed || disabled) return;
    setSubmitting(true);
    setError("");
    try { await onConfirm(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Operation failed"); }
    finally { setSubmitting(false); }
  }
  return (
    <form className="portal-confirm" onSubmit={(event: FormEvent<HTMLFormElement>) => void submit(event)}>
      <h3>{title}</h3><p>{description}</p>
      <label><input type="checkbox" checked={confirmed} onChange={(event: ChangeEvent<HTMLInputElement>) => setConfirmed(event.target.checked)} /> I reviewed the impact and intend to continue.</label>
      {error ? <p className="portal-error" role="alert">{error}</p> : null}
      <button type="submit" disabled={!confirmed || disabled || submitting}>{submitting ? "Working…" : confirmLabel}</button>
    </form>
  );
}

export function formatLabel(value: string): string {
  return value
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function formatMoney(minor: number, currency = "USD"): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(minor / 100);
}

export function formatDate(value: string | Date | null | undefined): string {
  if (!value) return "—";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" }).format(date);
}
