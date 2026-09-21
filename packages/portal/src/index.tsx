"use client";

import { FormEvent, useEffect, useState } from "react";

export type PortalRole = "vendor_admin" | "operations" | "finance" | "admin";
export interface PortalSection { label: string; path?: string; description: string }
export interface PortalConfig {
  name: string;
  eyebrow: string;
  allowedRoles: PortalRole[];
  sections: PortalSection[];
}

type User = { email: string; full_name: string; role: string };
type Session = { user: User };

const apiBase = () => {
  const value = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!value) throw new Error("A secure API origin is required");
  const origin = new URL(value);
  const loopback = ["localhost", "127.0.0.1", "::1"].includes(origin.hostname);
  if (origin.protocol !== "https:" && !(origin.protocol === "http:" && loopback)) {
    throw new Error("A secure API origin is required");
  }
  return value.replace(/\/$/, "");
};

async function request<T>(path: string, token?: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("Accept", "application/json");
  if (init?.body) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init?.method && !["GET", "HEAD", "OPTIONS"].includes(init.method)) {
    const csrf = document.cookie.split("; ").find((item) => item.startsWith("breero_csrf="))?.split("=")[1];
    if (csrf) headers.set("X-CSRF-Token", decodeURIComponent(csrf));
  }
  const response = await fetch(`${apiBase()}${path}`, { ...init, headers, cache: "no-store", credentials: "include" });
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as { message?: string; detail?: string; error?: { message?: string } };
    throw new Error(body.error?.message ?? body.message ?? body.detail ?? `Request failed (${response.status})`);
  }
  return response.status === 204 ? undefined as T : response.json() as Promise<T>;
}

function safeRows(value: unknown): Record<string, unknown>[] {
  if (Array.isArray(value)) return value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object");
  if (value && typeof value === "object" && "items" in value && Array.isArray((value as { items: unknown }).items)) {
    return (value as { items: unknown[] }).items.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object");
  }
  return value && typeof value === "object" ? [value as Record<string, unknown>] : [];
}

export function PortalApp({ config }: { config: PortalConfig }) {
  const [session, setSession] = useState<Session | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [active, setActive] = useState(config.sections[0]);
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    request<User>("/auth/me").then((user) => setSession({ user })).catch(() => setSession(null));
  }, []);

  async function login(event: FormEvent) {
    event.preventDefault(); setError("");
    try {
      const next = await request<Session>("/auth/browser/login", undefined, { method: "POST", body: JSON.stringify({ email, password }) });
      if (!config.allowedRoles.includes(next.user.role as PortalRole)) throw new Error("This account is not authorized for this portal.");
      setSession(next);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Sign in failed"); }
  }

  async function load(section: PortalSection) {
    setActive(section); setRows([]); setError("");
    if (!section.path || !session) return;
    setLoading(true);
    try { setRows(safeRows(await request<unknown>(section.path))); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to load data"); }
    finally { setLoading(false); }
  }

  async function logout() {
    if (!session) return;
    setError("");
    try {
      await request<void>("/auth/browser/logout", undefined, {
        method: "POST",
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to sign out securely");
      return;
    }
    setSession(null);
  }

  if (!session) return <main className="portal-login"><section className="portal-login__card" aria-labelledby="login-title">
    <p className="portal-eyebrow">{config.eyebrow}</p><h1 id="login-title">{config.name}</h1>
    <p>Sign in with an authorized BREERO account. This portal uses the live BREERO API and never displays fixture data.</p>
    <form onSubmit={login}><label>Email<input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} /></label>
      <label>Password<input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} /></label>
      {error && <p className="portal-error" role="alert">{error}</p>}<button type="submit">Sign in</button></form>
    <a href="https://breero.com">Return to BREERO</a>
  </section></main>;

  return <div className="portal-shell"><aside><a className="portal-brand" href="https://breero.com" aria-label="BREERO home">BREERO</a>
    <p>{config.name}</p><nav aria-label="Portal navigation">{config.sections.map((section) => <button key={section.label} className={active.label === section.label ? "is-active" : ""} onClick={() => void load(section)}>{section.label}</button>)}</nav>
    <button className="portal-signout" onClick={() => void logout()}>Sign out</button></aside>
    <main><header><div><p className="portal-eyebrow">{config.eyebrow}</p><h1>{active.label}</h1></div><p>{session.user.full_name}<br/><small>{session.user.email}</small></p></header>
      <section className="portal-panel"><h2>{active.label}</h2><p>{active.description}</p>
        {!active.path && <div className="portal-notice">This capability is not exposed by the canonical API yet. No placeholder data is shown.</div>}
        {loading && <p role="status">Loading live data…</p>}{error && <p className="portal-error" role="alert">{error}</p>}
        {active.path && !loading && !error && rows.length === 0 && <p className="portal-empty">No records are currently available.</p>}
        {rows.length > 0 && <div className="portal-table-wrap"><table><thead><tr>{Object.keys(rows[0]).slice(0, 6).map((key) => <th key={key}>{key.replaceAll("_", " ")}</th>)}</tr></thead>
          <tbody>{rows.map((row, index) => <tr key={String(row.id ?? index)}>{Object.keys(rows[0]).slice(0, 6).map((key) => <td key={key}>{typeof row[key] === "object" ? JSON.stringify(row[key]) : String(row[key] ?? "—")}</td>)}</tr>)}</tbody></table></div>}
      </section></main></div>;
}
