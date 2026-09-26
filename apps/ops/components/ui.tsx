import type { ReactNode } from "react";
import { RISK_LABELS, SEVERITY_LABELS, formatDateTime, statusLabel } from "../lib/format";
import type { Risk, RiskSeverity } from "../lib/types";

export function StatusBadge({ status }: { status: string }) {
  return <span className={`ops-badge ops-status ops-status--${status.toLowerCase()}`}>{statusLabel(status)}</span>;
}

export function SeverityBadge({ severity }: { severity: RiskSeverity | null }) {
  if (!severity) return <span className="ops-badge ops-severity ops-severity--none">On track</span>;
  return <span className={`ops-badge ops-severity ops-severity--${severity.toLowerCase()}`}>{SEVERITY_LABELS[severity]}</span>;
}

export function RiskList({ risks }: { risks: Risk[] }) {
  if (risks.length === 0) return <span className="ops-muted">No policy findings</span>;
  return (
    <ul className="ops-risks">
      {risks.map((risk) => (
        <li key={risk.code} title={risk.detail}>
          <SeverityBadge severity={risk.severity} /> {RISK_LABELS[risk.code] ?? risk.code}
        </li>
      ))}
    </ul>
  );
}

export function Stat({ label, value, tone, hint }: { label: string; value: number | string; tone?: "alert" | "warn" | "ok"; hint?: string }) {
  return (
    <div className={`ops-stat${tone ? ` ops-stat--${tone}` : ""}`}>
      <span className="ops-stat__label">{label}</span>
      <strong className="ops-stat__value">{value}</strong>
      {hint && <span className="ops-stat__hint">{hint}</span>}
    </div>
  );
}

export function Panel({ title, actions, children }: { title: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <section className="ops-panel" aria-label={title}>
      <header className="ops-panel__header"><h2>{title}</h2>{actions}</header>
      {children}
    </section>
  );
}

export function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="ops-error" role="alert">
      <span>{message}</span>
      {onRetry && <button type="button" className="ops-button ops-button--ghost" onClick={onRetry}>Retry</button>}
    </div>
  );
}

export function Loading({ label = "Loading live data…" }: { label?: string }) {
  return <p className="ops-loading" role="status">{label}</p>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="ops-empty">{children}</p>;
}

export function Notice({ children }: { children: ReactNode }) {
  return <p className="ops-notice">{children}</p>;
}

export function Freshness({ generatedAt, onRefresh, loading }: { generatedAt?: string; onRefresh: () => void; loading: boolean }) {
  return (
    <div className="ops-freshness">
      {generatedAt && <span>Server data as of {formatDateTime(generatedAt)}</span>}
      <button type="button" className="ops-button ops-button--ghost" onClick={onRefresh} disabled={loading}>
        {loading ? "Refreshing…" : "Refresh"}
      </button>
    </div>
  );
}
