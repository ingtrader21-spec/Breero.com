"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useContext, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { createAdminApi, resolveApiBase, toApiError, type AdminApi } from "../lib/api";
import { isActivePath, NAVIGATION } from "../lib/navigation";
import { canUseAdminPortal, parseSession, SESSION_KEY, type AdminSession } from "../lib/session";

interface AdminContextValue { api: AdminApi; session: AdminSession }
const AdminContext = createContext<AdminContextValue | null>(null);

export function useAdmin(): AdminContextValue {
  const value = useContext(AdminContext);
  if (!value) throw new Error("useAdmin must be used inside AdminShell");
  return value;
}

function apiBaseOrError(): { base: string | null; error: string | null } {
  try {
    return { base: resolveApiBase(process.env.NEXT_PUBLIC_API_BASE_URL), error: null };
  } catch (error) {
    return { base: null, error: error instanceof Error ? error.message : "API origin is not configured" };
  }
}

export function AdminShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() ?? "/";
  const [session, setSession] = useState<AdminSession | null>(null);
  const [ready, setReady] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const { base, error: configError } = useMemo(() => apiBaseOrError(), []);

  useEffect(() => {
    const stored = parseSession(sessionStorage.getItem(SESSION_KEY));
    if (stored && canUseAdminPortal(stored)) setSession(stored);
    else sessionStorage.removeItem(SESSION_KEY);
    setReady(true);
  }, []);

  const api = useMemo(() => (base && session ? createAdminApi({ baseUrl: base, token: session.access_token }) : null), [base, session]);

  async function login(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (!base) { setError(configError ?? "API origin is not configured"); return; }
    try {
      const response = await fetch(`${base}/auth/login`, {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
        cache: "no-store",
      });
      if (!response.ok) throw await toApiError(response);
      const next = parseSession(JSON.stringify(await response.json()));
      if (!next) throw new Error("Unexpected sign-in response");
      if (!canUseAdminPortal(next)) throw new Error("This account is not authorized for the admin portal.");
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(next));
      setPassword("");
      setSession(next);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Sign in failed");
    }
  }

  function signOut() {
    sessionStorage.removeItem(SESSION_KEY);
    setSession(null);
  }

  if (!ready) return <main className="portal-login"><p role="status">Loading…</p></main>;

  if (!session || !api) {
    return (
      <main className="portal-login">
        <section className="portal-login__card" aria-labelledby="login-title">
          <p className="portal-eyebrow">Governance workspace</p>
          <h1 id="login-title">Admin &amp; Finance</h1>
          <p>Sign in with an authorized BREERO administrator or finance account. Identity is verified by the configured identity provider; this portal never shows fixture data.</p>
          {configError && <p className="portal-error" role="alert">{configError}</p>}
          <form onSubmit={login}>
            <label>Email<input type="email" autoComplete="username" required value={email} onChange={(event) => setEmail(event.target.value)} /></label>
            <label>Password<input type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} /></label>
            {error && <p className="portal-error" role="alert">{error}</p>}
            <button type="submit">Sign in</button>
          </form>
        </section>
      </main>
    );
  }

  const groups = [...new Set(NAVIGATION.map((item) => item.group))];
  return (
    <AdminContext.Provider value={{ api, session }}>
      <div className="portal-shell">
        <aside>
          <a className="portal-brand" href="https://breero.com" aria-label="BREERO home">BREERO</a>
          <p>Admin &amp; Finance</p>
          <nav aria-label="Admin navigation" className="admin-nav">
            {groups.map((group) => (
              <div key={group}>
                <p className="admin-nav__group">{group}</p>
                {NAVIGATION.filter((item) => item.group === group).map((item) => (
                  <Link key={item.href} href={item.href} className={isActivePath(pathname, item.href) ? "is-active" : ""} aria-current={isActivePath(pathname, item.href) ? "page" : undefined}>
                    {item.label}
                  </Link>
                ))}
              </div>
            ))}
          </nav>
          <p className="admin-identity">{session.user.full_name}<br /><small>{session.user.email}</small></p>
          <button type="button" className="portal-signout" onClick={signOut}>Sign out</button>
        </aside>
        <main>{children}</main>
      </div>
    </AdminContext.Provider>
  );
}

export function PageHeader({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) {
  return (
    <header>
      <div>
        <p className="portal-eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
      </div>
      {children}
    </header>
  );
}
