"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useState, type FormEvent } from "react";
import { PageHeader, useAdmin } from "../../../../components/AdminShell";
import { ConfirmAction } from "../../../../components/ConfirmAction";
import { Empty, ErrorMessage, KeyValues, Loading, Notice, Section, StatusBadge } from "../../../../components/ui";
import { formatDateTime } from "../../../../lib/format";
import { describeCoverage, parsePostalCodeList } from "../../../../lib/geography";
import type { ServiceZone } from "../../../../lib/types";
import { useResource } from "../../../../lib/useResource";

export default function ServiceZonePage() {
  const params = useParams<{ zoneId: string }>();
  const zoneId = params?.zoneId ?? "";
  const { api } = useAdmin();
  const loader = useCallback(() => api.zoneCoverage(zoneId), [api, zoneId]);
  const { data, error, loading, reload } = useResource(zoneId ? loader : null);
  const zone = data?.service_zone;

  return (
    <>
      <PageHeader eyebrow="Service zones" title={zone?.name ?? "Service zone"}>
        <p><Link href="/geography">← All zones</Link></p>
      </PageHeader>
      <Loading active={loading && !zone} />
      <ErrorMessage error={error} />
      {zone && data && (
        <>
          <Section title="Coverage">
            <KeyValues rows={[
              { label: "Status", value: <StatusBadge value={zone.active ? "active" : "inactive"} tone={zone.active ? "success" : "neutral"} /> },
              { label: "Coverage", value: describeCoverage(zone).join(" · ") },
              { label: "Services offered", value: String(data.service_ids.length) },
              { label: "Priority", value: String(zone.priority) },
              { label: "Regular service", value: zone.regular_service_enabled ? "Enabled" : "Disabled" },
              { label: "Emergency service", value: zone.emergency_enabled ? "Enabled" : "Disabled" },
              { label: "Version", value: String(zone.version) },
              { label: "Updated", value: formatDateTime(zone.updated_at) },
            ]} />
            <h3>Postal codes ({data.postal_codes.length})</h3>
            {data.postal_codes.length ? (
              <ul className="admin-tag-list">
                {data.postal_codes.map((code) => <li key={code.id}>{code.postal_code}{code.active ? "" : " (inactive)"}</li>)}
              </ul>
            ) : <Empty>No postal codes are attached to this zone.</Empty>}
            <p><Link href={`/geography/postal-codes?zone=${zone.id}`}>Manage postal codes for this zone →</Link></p>
          </Section>
          {/* Key on version so the form resets after every successful change. */}
          <EditZone key={zone.version} zone={zone} onSaved={reload} />
        </>
      )}
    </>
  );
}

function EditZone({ zone, onSaved }: { zone: ServiceZone; onSaved: () => void }) {
  const { api } = useAdmin();
  const [name, setName] = useState(zone.name);
  const [priority, setPriority] = useState(String(zone.priority));
  const [city, setCity] = useState(zone.city ?? "");
  const [stateCode, setStateCode] = useState(zone.state_code ?? "");
  const [codes, setCodes] = useState(zone.postal_codes.join(", "));
  const [regular, setRegular] = useState(zone.regular_service_enabled);
  const [emergency, setEmergency] = useState(zone.emergency_enabled);
  const [errors, setErrors] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const problems: string[] = [];
    const parsed = parsePostalCodeList(codes);
    if (parsed.invalid.length) problems.push(`Invalid postal codes: ${parsed.invalid.join(", ")}.`);
    const priorityValue = Number(priority);
    if (!Number.isInteger(priorityValue) || priorityValue < 0 || priorityValue > 10000) problems.push("Priority must be 0–10000.");
    if (!name.trim()) problems.push("Name is required.");
    setErrors(problems);
    if (problems.length) return;
    const payload: Record<string, unknown> = {};
    if (name.trim() !== zone.name) payload.name = name.trim();
    if (priorityValue !== zone.priority) payload.priority = priorityValue;
    if ((city.trim() || null) !== zone.city) payload.city = city.trim() || null;
    if ((stateCode.trim().toUpperCase() || null) !== zone.state_code) payload.state_code = stateCode.trim().toUpperCase() || null;
    if (parsed.codes.join(",") !== zone.postal_codes.join(",")) payload.postal_codes = parsed.codes;
    if (regular !== zone.regular_service_enabled) payload.regular_service_enabled = regular;
    if (emergency !== zone.emergency_enabled) payload.emergency_enabled = emergency;
    if (Object.keys(payload).length === 0) { setErrors(["Nothing changed."]); return; }
    setBusy(true);
    try {
      await api.updateZone(zone.id, zone.version, payload);
      onSaved();
    } catch (reason) {
      setErrors([reason instanceof Error ? reason.message : "Unable to update zone"]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Section title="Update zone">
      <p>Updates use optimistic concurrency (If-Match version {zone.version}); if someone else changed this zone, reload and try again.</p>
      <form className="admin-form" onSubmit={submit}>
        <label>Name<input required maxLength={160} value={name} onChange={(event) => setName(event.target.value)} /></label>
        <div className="admin-form admin-form--inline">
          <label>State code<input maxLength={3} value={stateCode} onChange={(event) => setStateCode(event.target.value)} /></label>
          <label>City<input maxLength={120} value={city} onChange={(event) => setCity(event.target.value)} /></label>
          <label>Priority<input inputMode="numeric" value={priority} onChange={(event) => setPriority(event.target.value)} /></label>
        </div>
        <label>Postal codes<textarea rows={3} value={codes} onChange={(event) => setCodes(event.target.value)} /></label>
        <label className="admin-check"><input type="checkbox" checked={regular} onChange={(event) => setRegular(event.target.checked)} />Regular service</label>
        <label className="admin-check"><input type="checkbox" checked={emergency} onChange={(event) => setEmergency(event.target.checked)} />Emergency service</label>
        {errors.length > 0 && <Notice tone="danger"><ul>{errors.map((message) => <li key={message}>{message}</li>)}</ul></Notice>}
        <div className="admin-actions">
          <button type="submit" className="admin-button admin-button--primary" disabled={busy}>{busy ? "Saving…" : "Save changes"}</button>
        </div>
      </form>
      {zone.active && (
        <ConfirmAction
          label="Deactivate zone"
          title={`Deactivate ${zone.name}?`}
          description="Coverage checks will stop matching this zone. The zone record is kept and can be reactivated later."
          confirmLabel="Deactivate"
          tone="danger"
          onConfirm={async () => { await api.deactivateZone(zone.id, zone.version); onSaved(); }}
        />
      )}
      {!zone.active && (
        <ConfirmAction
          label="Reactivate zone"
          title={`Reactivate ${zone.name}?`}
          description="Coverage checks will match this zone again."
          confirmLabel="Reactivate"
          onConfirm={async () => { await api.updateZone(zone.id, zone.version, { active: true }); onSaved(); }}
        />
      )}
    </Section>
  );
}
