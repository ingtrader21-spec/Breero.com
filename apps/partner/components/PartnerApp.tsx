"use client";

import { type FormEvent, useEffect, useMemo, useState } from "react";

import { login, PartnerApi, resolveApiBase } from "../lib/api";
import { errorMessage } from "../lib/format";
import { clearSession, isPartnerSession, readSession, writeSession } from "../lib/session";
import type { Session } from "../lib/types";
import { AvailabilitySection } from "./sections/AvailabilitySection";
import { FinanceSection } from "./sections/FinanceSection";
import { OnboardingSection } from "./sections/OnboardingSection";
import { ProfileSection } from "./sections/ProfileSection";
import { QualificationsSection } from "./sections/QualificationsSection";
import { ServicesSection } from "./sections/ServicesSection";
import { SkillsSection } from "./sections/SkillsSection";
import { TeamSection } from "./sections/TeamSection";
import { WorkSection } from "./sections/WorkSection";

export type SectionKey =
  | "onboarding"
  | "profile"
  | "services"
  | "skills"
  | "team"
  | "availability"
  | "qualifications"
  | "work"
  | "finance";

export const SECTIONS: { key: SectionKey; label: string }[] = [
  { key: "onboarding", label: "Onboarding" },
  { key: "profile", label: "Company profile" },
  { key: "services", label: "Services" },
  { key: "skills", label: "Skills" },
  { key: "team", label: "Team" },
  { key: "availability", label: "Availability" },
  { key: "qualifications", label: "Qualifications" },
  { key: "work", label: "Jobs & offers" },
  { key: "finance", label: "Earnings & payouts" },
];

export interface SectionProps {
  api: PartnerApi;
  navigate: (key: SectionKey) => void;
}

function renderSection(key: SectionKey, props: SectionProps) {
  switch (key) {
    case "onboarding": return <OnboardingSection {...props} />;
    case "profile": return <ProfileSection {...props} />;
    case "services": return <ServicesSection {...props} />;
    case "skills": return <SkillsSection {...props} />;
    case "team": return <TeamSection {...props} />;
    case "availability": return <AvailabilitySection {...props} />;
    case "qualifications": return <QualificationsSection {...props} />;
    case "work": return <WorkSection {...props} />;
    case "finance": return <FinanceSection />;
  }
}

function LoginCard({ base, onSession }: { base: string; onSession: (session: Session) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const session = await login(base, email, password);
      if (!isPartnerSession(session)) throw new Error("This account is not authorized for the partner portal.");
      onSession(session);
    } catch (reason) {
      setError(errorMessage(reason, "Sign in failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="portal-login">
      <section className="portal-login__card" aria-labelledby="login-title">
        <p className="portal-eyebrow">Provider workspace</p>
        <h1 id="login-title">Partner Portal</h1>
        <p>Sign in with your BREERO provider account. Everything shown here comes from the live BREERO API.</p>
        <form onSubmit={submit}>
          <label>Email<input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} /></label>
          <label>Password<input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} /></label>
          {error && <p className="portal-error" role="alert">{error}</p>}
          <button type="submit" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        </form>
        <a href="https://breero.com">Return to BREERO</a>
      </section>
    </main>
  );
}

export function PartnerApp() {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const [active, setActive] = useState<SectionKey>("onboarding");

  const base = useMemo(() => {
    try {
      return { url: resolveApiBase(process.env.NEXT_PUBLIC_API_BASE_URL), error: "" };
    } catch (reason) {
      return { url: "", error: errorMessage(reason) };
    }
  }, []);

  useEffect(() => {
    setSession(readSession(window.sessionStorage));
    setReady(true);
  }, []);

  const api = useMemo(
    () =>
      session && base.url
        ? new PartnerApi(base.url, session.access_token, {
            onUnauthorized: () => {
              clearSession(window.sessionStorage);
              setSession(null);
            },
          })
        : null,
    [session, base.url],
  );

  if (!ready) return null;
  if (base.error) {
    return <main className="portal-login"><p className="portal-error" role="alert">{base.error}</p></main>;
  }
  if (!session || !api) {
    return (
      <LoginCard
        base={base.url}
        onSession={(next) => {
          writeSession(window.sessionStorage, next);
          setSession(next);
        }}
      />
    );
  }

  const current = SECTIONS.find((item) => item.key === active) ?? SECTIONS[0];
  return (
    <div className="portal-shell">
      <aside>
        <a className="portal-brand" href="https://breero.com" aria-label="BREERO home">BREERO</a>
        <p>Partner Portal</p>
        <nav aria-label="Partner navigation">
          {SECTIONS.map((item) => (
            <button
              key={item.key}
              type="button"
              className={item.key === active ? "is-active" : ""}
              aria-current={item.key === active ? "page" : undefined}
              onClick={() => setActive(item.key)}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <button
          type="button"
          className="portal-signout"
          onClick={() => {
            clearSession(window.sessionStorage);
            setSession(null);
          }}
        >
          Sign out
        </button>
      </aside>
      <main>
        <header>
          <div>
            <p className="portal-eyebrow">Provider workspace</p>
            <h1>{current.label}</h1>
          </div>
          <p>{session.user.full_name}<br /><small>{session.user.email}</small></p>
        </header>
        {renderSection(active, { api, navigate: setActive })}
      </main>
    </div>
  );
}
