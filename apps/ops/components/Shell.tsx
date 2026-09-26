"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { createOpsApi } from "../lib/api";
import { OPS_ROLES, SESSION_KEY, resolveApiBase } from "../lib/config";
import { OpsContext, errorMessage } from "../lib/session";
import type { OpsSession } from "../lib/types";

export const NAVIGATION = [
  { href: "/", label: "Dashboard" },
  { href: "/queue", label: "Dispatch queue" },
  { href: "/exceptions", label: "SLA & exceptions" },
  { href: "/capacity", label: "Capacity" },
  { href: "/service-areas", label: "Service areas" },
  { href: "/integrations", label: "Integration failures" },
] as const;

function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

function readSession(): OpsSession | null {
  const raw = sessionStorage.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as OpsSession;
    return parsed.access_token && parsed.user ? parsed : null;
  } catch {
    sessionStorage.removeItem(SESSION_KEY);
    return null;
  }
}

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [session, setSession] = useState<OpsSession | null>(null);
  const [ready, setReady] = useState(false);
  const baseUrl = useMemo(() => {
    try { return resolveApiBase({ NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL, NODE_ENV: process.env.NODE_ENV }); }
    catch { return null; }
  }, []);

  useEffect(() => {
    setSession(readSession());
    setReady(true);
  }, []);

  const signOut = useCallback(() => {
    sessionStorage.removeItem(SESSION_KEY);
    setSession(null);
  }, []);

  const api = useMemo(
    () => (baseUrl ? createOpsApi({ baseUrl, token: session?.access_token, onUnauthorized: signOut }) : null),
    [baseUrl, session?.access_token, signOut],
  );

  if (!baseUrl) return <main className="ops-login"><p className="ops-error" role="alert">This deployment has no secure API origin configured.</p></main>;
  if (!ready || !api) return <main className="ops-login"><p className="ops-loading" role="status">Loading…</p></main>;
  if (!session) {
    return (
      <LoginForm
        onLogin={async (email, password) => {
          const result = await api.login(email, password);
          if (!(OPS_ROLES as readonly string[]).includes(result.user.role)) throw new Error("This account is not authorized for BREERO Operations.");
          // Keep only what the console needs; the refresh token is never persisted.
          const next: OpsSession = { access_token: result.access_token, user: result.user };
          sessionStorage.setItem(SESSION_KEY, JSON.stringify(next));
          setSession(next);
        }}
      />
    );
  }

  return (
    <OpsContext.Provider value={{ session, api, signOut }}>
      <div className="ops-shell">
        <aside className="ops-sidebar">
          <Link className="ops-brand" href="/">BREERO <span>Operations</span></Link>
          <nav aria-label="Operations navigation">
            {NAVIGATION.map((item) => (
              <Link key={item.href} href={item.href} className={isActive(pathname, item.href) ? "is-active" : undefined} aria-current={isActive(pathname, item.href) ? "page" : undefined}>
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="ops-user">
            <span>{session.user.full_name}</span>
            <small>{session.user.email} · {session.user.role}</small>
            <button type="button" className="ops-button ops-button--ghost" onClick={signOut}>Sign out</button>
          </div>
        </aside>
        <main className="ops-main">{children}</main>
      </div>
    </OpsContext.Provider>
  );
}

function LoginForm({ onLogin }: { onLogin: (email: string, password: string) => Promise<void> }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try { await onLogin(email, password); }
    catch (reason) { setError(errorMessage(reason, "Sign in failed")); }
    finally { setBusy(false); }
  }

  return (
    <main className="ops-login">
      <section className="ops-login__card" aria-labelledby="ops-login-title">
        <p className="ops-eyebrow">Service operations</p>
        <h1 id="ops-login-title">BREERO Operations</h1>
        <p>Sign in with an authorized operations or admin account. Every screen reads live BREERO data; nothing is simulated.</p>
        <form onSubmit={submit}>
          <label>Email<input type="email" autoComplete="username" required value={email} onChange={(event) => setEmail(event.target.value)} /></label>
          <label>Password<input type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} /></label>
          {error && <p className="ops-error" role="alert">{error}</p>}
          <button type="submit" className="ops-button" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        </form>
      </section>
    </main>
  );
}
