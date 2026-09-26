"use client";

import Link from "next/link";
import { useCallback, useState, type FormEvent } from "react";
import { PageHeader, useAdmin } from "../../components/AdminShell";
import { Empty, ErrorMessage, Loading, Notice, Pager, Section, StatusBadge } from "../../components/ui";
import { buildZoneCreatePayload, describeCoverage, type ZoneFormValues } from "../../lib/geography";
import { useResource } from "../../lib/useResource";

const PAGE_SIZE = 25;
const EMPTY_FORM: ZoneFormValues = { legal_entity_id: "", name: "", state_code: "", city: "", postal_codes: "", priority: "100", regular_service_enabled: true, emergency_enabled: false };

export default function ServiceZonesPage() {
  const { api } = useAdmin();
  const [active, setActive] = useState<"" | "true" | "false">("true");
  const [stateCode, setStateCode] = useState("");
  const [page, setPage] = useState(1);
  const loader = useCallback(
    () => api.listZones({ active: active === "" ? undefined : active === "true", state_code: stateCode.trim() || undefined, page, page_size: PAGE_SIZE }),
    [api, active, stateCode, page],
  );
  const { data, error, loading, reload } = useResource(loader);

  return (
    <>
      <PageHeader eyebrow="Geography" title="Service zones" />
      <Notice title="No map view">
        Coverage is shown as postal codes, city/state selectors and radius metadata. A tile map would send zone coordinates to a third-party map host, so none is rendered.
      </Notice>
      <Section title="Zones">
        <div className="admin-form admin-form--inline">
          <label>Status
            <select value={active} onChange={(event) => { setPage(1); setActive(event.target.value as typeof active); }}>
              <option value="true">Active</option><option value="false">Inactive</option><option value="">All</option>
            </select>
          </label>
          <label>State<input value={stateCode} maxLength={3} onChange={(event) => { setPage(1); setStateCode(event.target.value.toUpperCase()); }} /></label>
        </div>
        <Loading active={loading} />
        <ErrorMessage error={error} />
        {data && data.items.length === 0 && <Empty>No service zones match.</Empty>}
        {data && data.items.length > 0 && (
          <>
            <div className="portal-table-wrap">
              <table>
                <thead><tr><th>Name</th><th>Status</th><th>Coverage</th><th>Services</th><th>Priority</th><th>Emergency</th></tr></thead>
                <tbody>
                  {data.items.map((zone) => (
                    <tr key={zone.id}>
                      <td><Link href={`/geography/zones/${zone.id}`}>{zone.name}</Link></td>
                      <td><StatusBadge value={zone.active ? "active" : "inactive"} tone={zone.active ? "success" : "neutral"} /></td>
                      <td>{describeCoverage(zone).join(" · ")}</td>
                      <td>{zone.service_ids.length}</td>
                      <td>{zone.priority}</td>
                      <td>{zone.emergency_enabled ? "Yes" : "No"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
          </>
        )}
      </Section>
      <CreateZone onCreated={reload} />
    </>
  );
}

function CreateZone({ onCreated }: { onCreated: () => void }) {
  const { api } = useAdmin();
  const [values, setValues] = useState<ZoneFormValues>(EMPTY_FORM);
  const [errors, setErrors] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setCreated(null);
    const { payload, errors: problems } = buildZoneCreatePayload(values);
    setErrors(problems);
    if (!payload) return;
    setBusy(true);
    try {
      const zone = await api.createZone(payload);
      setCreated(zone.name);
      setValues(EMPTY_FORM);
      onCreated();
    } catch (reason) {
      setErrors([reason instanceof Error ? reason.message : "Unable to create zone"]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Section title="Create service zone">
      <form className="admin-form" onSubmit={submit}>
        <label>Legal entity ID<input required value={values.legal_entity_id} onChange={(event) => setValues({ ...values, legal_entity_id: event.target.value })} /></label>
        <label>Name<input required maxLength={160} value={values.name} onChange={(event) => setValues({ ...values, name: event.target.value })} /></label>
        <div className="admin-form admin-form--inline">
          <label>State code<input maxLength={3} value={values.state_code} onChange={(event) => setValues({ ...values, state_code: event.target.value })} /></label>
          <label>City<input maxLength={120} value={values.city} onChange={(event) => setValues({ ...values, city: event.target.value })} /></label>
          <label>Priority<input inputMode="numeric" value={values.priority} onChange={(event) => setValues({ ...values, priority: event.target.value })} /></label>
        </div>
        <label>Postal codes (comma, space or newline separated)<textarea rows={3} value={values.postal_codes} onChange={(event) => setValues({ ...values, postal_codes: event.target.value })} /></label>
        <label className="admin-check"><input type="checkbox" checked={values.regular_service_enabled} onChange={(event) => setValues({ ...values, regular_service_enabled: event.target.checked })} />Regular service</label>
        <label className="admin-check"><input type="checkbox" checked={values.emergency_enabled} onChange={(event) => setValues({ ...values, emergency_enabled: event.target.checked })} />Emergency service</label>
        {errors.length > 0 && <Notice tone="danger" title="Zone not created"><ul>{errors.map((message) => <li key={message}>{message}</li>)}</ul></Notice>}
        {created && <Notice tone="success">Created {created}.</Notice>}
        <div className="admin-actions"><button type="submit" className="admin-button admin-button--primary" disabled={busy}>{busy ? "Creating…" : "Create zone"}</button></div>
      </form>
    </Section>
  );
}
