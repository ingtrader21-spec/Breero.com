"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { AuditApiError, auditGet, readAccessToken } from "./api";
import { AuditFilterError, defaultFilters, detailPath, formatMetadataValue, humanize, listPath, MAX_PAGE_SIZE, tracePath } from "./query";
import { AUDIT_CATEGORIES, type AuditCorrelationTrace, type AuditEventDetail, type AuditEventPage, type AuditFilters } from "./types";

type Panel = { kind: "detail"; event: AuditEventDetail } | { kind: "trace"; trace: AuditCorrelationTrace } | null;

function message(reason: unknown): string {
  if (reason instanceof AuditFilterError || reason instanceof AuditApiError) return reason.message;
  return "Unable to load audit records.";
}

function when(value: string): string {
  return new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "medium" });
}

function MetadataTable({ event }: { event: AuditEventDetail }) {
  const entries = Object.entries(event.metadata);
  return <>
    {entries.length === 0 ? <p className="portal-empty">No exposable metadata.</p> :
      <dl className="audit-metadata">{entries.map(([key, value]) => <div key={key}><dt>{humanize(key)}</dt><dd>{formatMetadataValue(value)}</dd></div>)}</dl>}
    {event.metadata_withheld_keys > 0 && <p className="portal-notice">{event.metadata_withheld_keys} stored field(s) withheld by the privacy allowlist.</p>}
  </>;
}

function EventDetail({ event, onTrace }: { event: AuditEventDetail; onTrace: (id: string) => void }) {
  return <section className="portal-panel" aria-labelledby="audit-detail-title">
    <h2 id="audit-detail-title">{event.action}</h2>
    <dl className="audit-metadata">
      <div><dt>When</dt><dd>{when(event.occurred_at)}</dd></div>
      <div><dt>Result</dt><dd>{event.result}</dd></div>
      <div><dt>Category</dt><dd>{humanize(event.category)}{event.security_relevant ? " (security)" : ""}</dd></div>
      <div><dt>Actor</dt><dd>{event.actor.type} · {event.actor.id ?? "anonymous"}</dd></div>
      <div><dt>Resource</dt><dd>{event.resource.type} · {event.resource.id}</dd></div>
      <div><dt>Provider</dt><dd>{event.vendor_id ?? "—"}</dd></div>
      <div><dt>Request ID</dt><dd>{event.request_id ?? "—"}</dd></div>
      <div><dt>Correlation ID</dt><dd>{event.correlation_id ?? "—"}</dd></div>
      <div><dt>Source fingerprint</dt><dd>{event.source_fingerprint ?? "—"}</dd></div>
    </dl>
    <h3>Metadata</h3>
    <MetadataTable event={event} />
    {event.correlation_id && <button type="button" onClick={() => onTrace(event.correlation_id as string)}>Trace correlation</button>}
  </section>;
}

export function AuditConsole() {
  const [token, setToken] = useState<string | null>(null);
  const [draft, setDraft] = useState<AuditFilters>(() => defaultFilters());
  const [applied, setApplied] = useState<AuditFilters | null>(null);
  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  const [page, setPage] = useState<AuditEventPage | null>(null);
  const [panel, setPanel] = useState<Panel>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => { setToken(readAccessToken()); }, []);

  const load = useCallback(async (filters: AuditFilters, cursor: string | null) => {
    if (!token) return;
    setLoading(true); setError("");
    try { setPage(await auditGet<AuditEventPage>(listPath(filters, cursor), token)); }
    catch (reason) { setPage(null); setError(message(reason)); }
    finally { setLoading(false); }
  }, [token]);

  useEffect(() => { if (applied) void load(applied, cursors[cursors.length - 1]); }, [applied, cursors, load]);

  function submit(event: FormEvent) {
    event.preventDefault(); setPanel(null);
    setApplied({ ...draft }); setCursors([null]);
  }

  async function open<T>(path: () => string, toPanel: (body: T) => Panel) {
    if (!token) return;
    setError("");
    try { setPanel(toPanel(await auditGet<T>(path(), token))); }
    catch (reason) { setError(message(reason)); }
  }
  const openDetail = (id: string) => void open<AuditEventDetail>(() => detailPath(id), (event) => ({ kind: "detail", event }));
  const openTrace = (id: string) => void open<AuditCorrelationTrace>(() => tracePath(id), (trace) => ({ kind: "trace", trace }));

  const update = <K extends keyof AuditFilters>(key: K, value: AuditFilters[K]) => setDraft((current) => ({ ...current, [key]: value }));

  if (!token) return <main className="portal-login"><section className="portal-login__card">
    <h1>Audit log</h1><p>Sign in to the admin portal first. This console reuses that session and never shows placeholder data.</p>
    <Link href="/">Go to admin sign-in</Link></section></main>;

  return <main className="audit-console">
    <header><p className="portal-eyebrow">Governance workspace</p><h1>Audit &amp; security activity</h1>
      <p>Read-only, admin-safe view of recorded actions. Metadata is limited to an allowlist; secrets, tokens and contact details are never shown.</p></header>

    <form className="portal-panel audit-filters" onSubmit={submit} aria-label="Audit filters">
      <fieldset><legend>View</legend>
        <label><input type="radio" name="view" checked={draft.view === "all"} onChange={() => update("view", "all")} /> All events</label>
        <label><input type="radio" name="view" checked={draft.view === "security"} onChange={() => update("view", "security")} /> Security activity</label>
      </fieldset>
      <label>From<input type="datetime-local" required value={draft.occurredFrom} onChange={(e) => update("occurredFrom", e.target.value)} /></label>
      <label>To<input type="datetime-local" required value={draft.occurredTo} onChange={(e) => update("occurredTo", e.target.value)} /></label>
      <label>Actor ID<input value={draft.actorId} onChange={(e) => update("actorId", e.target.value)} placeholder="UUID" /></label>
      <label>Action<input value={draft.action} onChange={(e) => update("action", e.target.value)} placeholder="payout.approve" /></label>
      <label><input type="checkbox" checked={draft.actionIsPrefix} onChange={(e) => update("actionIsPrefix", e.target.checked)} /> Match action prefix</label>
      <label>Resource type<input value={draft.resourceType} onChange={(e) => update("resourceType", e.target.value)} placeholder="payout_batch" /></label>
      <label>Resource ID<input value={draft.resourceId} onChange={(e) => update("resourceId", e.target.value)} placeholder="UUID" /></label>
      <label>Result<select value={draft.result} onChange={(e) => update("result", e.target.value as AuditFilters["result"])}>
        <option value="">Any</option><option value="success">Success</option><option value="denied">Denied</option><option value="failure">Failure</option></select></label>
      <label>Event type<select value={draft.category} onChange={(e) => update("category", e.target.value as AuditFilters["category"])}>
        <option value="">Any</option>{AUDIT_CATEGORIES.map((category) => <option key={category} value={category}>{humanize(category)}</option>)}</select></label>
      <label>Correlation ID<input value={draft.correlationId} onChange={(e) => update("correlationId", e.target.value)} /></label>
      <label>Provider ID<input value={draft.vendorId} onChange={(e) => update("vendorId", e.target.value)} placeholder="UUID" /></label>
      <label>Page size<input type="number" min={1} max={MAX_PAGE_SIZE} value={draft.limit} onChange={(e) => update("limit", Number(e.target.value))} /></label>
      <button type="submit">Search</button>
    </form>

    {error && <p className="portal-error" role="alert">{error}</p>}
    {loading && <p role="status">Loading audit records…</p>}
    {applied && page && !loading && (page.items.length === 0 ? <p className="portal-empty">No audit records match these filters.</p> :
      <div className="portal-table-wrap"><table>
        <caption>{applied.view === "security" ? "Security activity" : "Audit events"} · {when(page.occurred_from)} – {when(page.occurred_to)}</caption>
        <thead><tr><th>When</th><th>Action</th><th>Result</th><th>Event type</th><th>Actor</th><th>Resource</th><th>Correlation</th><th>Details</th></tr></thead>
        <tbody>{page.items.map((item) => <tr key={item.id} className={item.result !== "success" ? "is-alert" : undefined}>
          <td>{when(item.occurred_at)}</td><td>{item.action}</td><td>{item.result}</td><td>{humanize(item.category)}</td>
          <td>{item.actor.type}</td><td>{item.resource.type}</td>
          <td>{item.correlation_id ? <button type="button" onClick={() => openTrace(item.correlation_id as string)}>{item.correlation_id}</button> : "—"}</td>
          <td><button type="button" onClick={() => openDetail(item.id)} aria-label={`View details for ${item.action}`}>Details</button></td>
        </tr>)}</tbody></table></div>)}

    {applied && page && <nav className="audit-pagination" aria-label="Audit pagination">
      <button type="button" disabled={cursors.length <= 1 || loading} onClick={() => setCursors((stack) => stack.slice(0, -1))}>Previous</button>
      <span>Page {cursors.length}</span>
      <button type="button" disabled={!page.next_cursor || loading} onClick={() => setCursors((stack) => [...stack, page.next_cursor])}>Next</button>
    </nav>}

    {panel?.kind === "detail" && <EventDetail event={panel.event} onTrace={openTrace} />}
    {panel?.kind === "trace" && <section className="portal-panel" aria-labelledby="audit-trace-title">
      <h2 id="audit-trace-title">Correlation {panel.trace.correlation_id}</h2>
      {panel.trace.truncated && <p className="portal-notice">Showing the first {panel.trace.items.length} events only.</p>}
      <ol className="audit-trace">{panel.trace.items.map((event) => <li key={event.id}>
        <button type="button" onClick={() => setPanel({ kind: "detail", event })}>{when(event.occurred_at)} · {event.action} · {event.result}</button>
      </li>)}</ol>
    </section>}
  </main>;
}
