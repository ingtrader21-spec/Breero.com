import type { ReactNode } from "react";
import type { Tone } from "../lib/payouts";
import { humanize } from "../lib/format";

export function StatusBadge({ value, tone = "neutral" }: { value: string; tone?: Tone }) {
  return <span className={`admin-badge admin-badge--${tone}`}>{humanize(value)}</span>;
}

export function Notice({ children, tone = "info", title }: { children: ReactNode; tone?: Tone; title?: string }) {
  return (
    <div className={`admin-notice admin-notice--${tone}`} role={tone === "danger" ? "alert" : "note"}>
      {title && <strong>{title}</strong>}
      <div>{children}</div>
    </div>
  );
}

export function ErrorMessage({ error }: { error: string | null }) {
  return error ? <p className="portal-error" role="alert">{error}</p> : null;
}

export function Loading({ active, label = "Loading live data…" }: { active: boolean; label?: string }) {
  return active ? <p role="status">{label}</p> : null;
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="portal-empty">{children}</p>;
}

export function KeyValues({ rows }: { rows: { label: string; value: ReactNode }[] }) {
  return (
    <dl className="admin-kv">
      {rows.map((row) => (
        <div key={row.label}>
          <dt>{row.label}</dt>
          <dd>{row.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Pager({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (page: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <nav className="admin-pager" aria-label="Pagination">
      <button type="button" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</button>
      <span>Page {page} of {pages} · {total} total</span>
      <button type="button" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</button>
    </nav>
  );
}

export function Section({ title, children, actions }: { title: string; children: ReactNode; actions?: ReactNode }) {
  return (
    <section className="portal-panel">
      <div className="admin-section-head">
        <h2>{title}</h2>
        {actions}
      </div>
      {children}
    </section>
  );
}
