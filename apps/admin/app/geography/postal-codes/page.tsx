"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useState, type FormEvent } from "react";
import { PageHeader, useAdmin } from "../../../components/AdminShell";
import { ConfirmAction } from "../../../components/ConfirmAction";
import { Empty, ErrorMessage, KeyValues, Loading, Notice, Pager, Section, StatusBadge } from "../../../components/ui";
import { newIdempotencyKey } from "../../../lib/api";
import { normalizePostalCode, parsePostalCodeCsv, type ImportParseResult } from "../../../lib/geography";
import type { PostalCode, PostalCodeImportResult } from "../../../lib/types";
import { useResource } from "../../../lib/useResource";

const PAGE_SIZE = 25;
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default function PostalCodesPage() {
  return (
    <Suspense fallback={<p role="status">Loading…</p>}>
      <PostalCodes />
    </Suspense>
  );
}

function PostalCodes() {
  const { api } = useAdmin();
  const search = useSearchParams();
  const [zoneId, setZoneId] = useState(search?.get("zone") ?? "");
  const [postal, setPostal] = useState("");
  const [page, setPage] = useState(1);
  const validZone = UUID_RE.test(zoneId.trim()) ? zoneId.trim() : undefined;
  const normalizedPostal = postal.trim() ? normalizePostalCode(postal) ?? undefined : undefined;
  const loader = useCallback(
    () => api.listPostalCodes({ service_area_id: validZone, postal_code: normalizedPostal, page, page_size: PAGE_SIZE }),
    [api, validZone, normalizedPostal, page],
  );
  const { data, error, loading, reload } = useResource(loader);

  return (
    <>
      <PageHeader eyebrow="Geography" title="Postal codes" />
      <Section title="Coverage rows">
        <div className="admin-form admin-form--inline">
          <label>Service zone ID<input value={zoneId} onChange={(event) => { setPage(1); setZoneId(event.target.value); }} /></label>
          <label>Postal code<input value={postal} maxLength={10} onChange={(event) => { setPage(1); setPostal(event.target.value); }} /></label>
        </div>
        {zoneId.trim() && !validZone && <Notice tone="warning">Enter a full service zone UUID to filter by zone.</Notice>}
        <Loading active={loading} />
        <ErrorMessage error={error} />
        {data && data.items.length === 0 && <Empty>No postal codes match.</Empty>}
        {data && data.items.length > 0 && (
          <>
            <div className="portal-table-wrap">
              <table>
                <thead><tr><th>Postal code</th><th>City</th><th>State</th><th>Status</th><th>Emergency</th><th>Action</th></tr></thead>
                <tbody>
                  {data.items.map((row) => <PostalRow key={row.id} row={row} onChanged={reload} />)}
                </tbody>
              </table>
            </div>
            <Pager page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
          </>
        )}
      </Section>
      <CreatePostalCode defaultZone={validZone ?? ""} onCreated={reload} />
      <ImportPostalCodes defaultZone={validZone ?? ""} onImported={reload} />
    </>
  );
}

function PostalRow({ row, onChanged }: { row: PostalCode; onChanged: () => void }) {
  const { api } = useAdmin();
  return (
    <tr>
      <td>{row.postal_code}</td>
      <td>{row.city ?? "—"}</td>
      <td>{row.state_code ?? "—"}</td>
      <td><StatusBadge value={row.active ? "active" : "inactive"} tone={row.active ? "success" : "neutral"} /></td>
      <td>{row.emergency_service_enabled ? "Yes" : "No"}</td>
      <td>
        {row.active ? (
          <ConfirmAction
            label="Deactivate"
            title={`Deactivate ${row.postal_code}?`}
            description="Coverage checks will stop matching this postal code in its zone."
            confirmLabel="Deactivate"
            tone="danger"
            onConfirm={async () => { await api.deactivatePostalCode(row.id, row.version); onChanged(); }}
          />
        ) : (
          <ConfirmAction
            label="Reactivate"
            title={`Reactivate ${row.postal_code}?`}
            description="Coverage checks will match this postal code again."
            confirmLabel="Reactivate"
            onConfirm={async () => { await api.updatePostalCode(row.id, row.version, { active: true }); onChanged(); }}
          />
        )}
      </td>
    </tr>
  );
}

function CreatePostalCode({ defaultZone, onCreated }: { defaultZone: string; onCreated: () => void }) {
  const { api } = useAdmin();
  const [zone, setZone] = useState(defaultZone);
  const [code, setCode] = useState("");
  const [city, setCity] = useState("");
  const [stateCode, setStateCode] = useState("");
  const [emergency, setEmergency] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setDone(null);
    const postal = normalizePostalCode(code);
    if (!UUID_RE.test(zone.trim())) { setError("Service zone ID must be a UUID."); return; }
    if (!postal) { setError("Postal code must use ZIP or ZIP+4 format."); return; }
    try {
      const created = await api.createPostalCode({
        service_area_id: zone.trim(),
        postal_code: postal,
        city: city.trim() || null,
        state_code: stateCode.trim().toUpperCase() || null,
        emergency_service_enabled: emergency,
      });
      setError(null);
      setDone(`Added ${created.postal_code}.`);
      setCode("");
      onCreated();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to add postal code");
    }
  }

  return (
    <Section title="Add postal code">
      <form className="admin-form admin-form--inline" onSubmit={submit}>
        <label>Service zone ID<input required value={zone} onChange={(event) => setZone(event.target.value)} /></label>
        <label>Postal code<input required maxLength={10} value={code} onChange={(event) => setCode(event.target.value)} /></label>
        <label>City<input maxLength={120} value={city} onChange={(event) => setCity(event.target.value)} /></label>
        <label>State<input maxLength={3} value={stateCode} onChange={(event) => setStateCode(event.target.value)} /></label>
        <label className="admin-check"><input type="checkbox" checked={emergency} onChange={(event) => setEmergency(event.target.checked)} />Emergency</label>
        <button type="submit" className="admin-button admin-button--primary">Add</button>
      </form>
      <ErrorMessage error={error} />
      {done && <Notice tone="success">{done}</Notice>}
    </Section>
  );
}

function ImportPostalCodes({ defaultZone, onImported }: { defaultZone: string; onImported: () => void }) {
  const { api } = useAdmin();
  const [zone, setZone] = useState(defaultZone);
  const [parsed, setParsed] = useState<ImportParseResult | null>(null);
  const [result, setResult] = useState<PostalCodeImportResult | null>(null);
  // One key per validated file: retries of the same file are idempotent server-side.
  const [idempotencyKey, setIdempotencyKey] = useState<string | null>(null);

  async function onFile(file: File | undefined) {
    setResult(null);
    if (!file) { setParsed(null); return; }
    const next = parsePostalCodeCsv(await file.text());
    setParsed(next);
    setIdempotencyKey(next.errors.length ? null : newIdempotencyKey("postal-import"));
  }

  const ready = parsed && parsed.errors.length === 0 && parsed.rows.length > 0 && UUID_RE.test(zone.trim()) && idempotencyKey;

  return (
    <Section title="Import postal codes (CSV)">
      <p>Header: <code>postal_code,city,state_code,active,regular_service_enabled,emergency_service_enabled,priority</code>. Only <code>postal_code</code> is required. The file is validated locally before anything is sent.</p>
      <div className="admin-form admin-form--inline">
        <label>Service zone ID<input value={zone} onChange={(event) => setZone(event.target.value)} /></label>
        <label>CSV file<input type="file" accept=".csv,text/csv" onChange={(event) => void onFile(event.target.files?.[0])} /></label>
      </div>
      {parsed && parsed.errors.length > 0 && (
        <Notice tone="danger" title="File rejected"><ul>{parsed.errors.slice(0, 20).map((message) => <li key={message}>{message}</li>)}</ul></Notice>
      )}
      {parsed && parsed.errors.length === 0 && <Notice tone="success">{parsed.rows.length} valid row(s) ready to import.</Notice>}
      <ConfirmAction
        label="Import"
        title="Import these postal codes?"
        description={`${parsed?.rows.length ?? 0} row(s) will be applied to zone ${zone.trim() || "—"}. Re-submitting the same file reuses the same Idempotency-Key.`}
        confirmLabel="Import"
        disabled={!ready}
        onConfirm={async () => {
          if (!parsed || !idempotencyKey) return;
          setResult(await api.importPostalCodes(zone.trim(), parsed.rows, idempotencyKey));
          onImported();
        }}
      />
      {result && (
        <KeyValues rows={[
          { label: "Import status", value: <StatusBadge value={result.status} tone={result.status === "COMPLETED" ? "success" : result.status === "FAILED" ? "danger" : "info"} /> },
          { label: "Total rows", value: String(result.total_rows) },
          { label: "Imported", value: String(result.imported_rows) },
          { label: "Rejected", value: String(result.rejected_rows) },
        ]} />
      )}
    </Section>
  );
}
