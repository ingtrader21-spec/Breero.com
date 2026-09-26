"use client";

import { type FormEvent, useCallback, useState } from "react";

import { formatDate, todayIso } from "../../lib/format";
import {
  canEditQualification,
  canSubmitQualification,
  emptyQualificationDraft,
  QUALIFICATION_TYPES,
  type QualificationDraft,
  qualificationStatusView,
  validateQualificationDraft,
} from "../../lib/qualifications";
import type { Qualification, QualificationType } from "../../lib/types";
import type { SectionProps } from "../PartnerApp";
import { Alert, Empty, Field, Loading, Panel, StatusBadge, useAction, useResource } from "../ui";

function toDraft(item: Qualification): QualificationDraft {
  return {
    qualificationType: item.qualification_type,
    title: item.title,
    issuer: item.issuer ?? "",
    jurisdiction: item.jurisdiction ?? "",
    referenceLast4: item.reference_last4 ?? "",
    issuedOn: item.issued_on ?? "",
    expiresOn: item.expires_on ?? "",
    evidenceReference: item.evidence_reference ?? "",
    workerId: item.worker_id ?? "",
  };
}

export function QualificationsSection({ api }: SectionProps) {
  const load = useCallback(async () => {
    const [list, workers] = await Promise.all([api.qualifications(), api.workers()]);
    return { list, workers: workers.items };
  }, [api]);
  const resource = useResource(load);
  const action = useAction();
  const [draft, setDraft] = useState<QualificationDraft>(emptyQualificationDraft);
  const [editing, setEditing] = useState<Qualification | null>(null);
  const [errors, setErrors] = useState<string[]>([]);

  if (resource.loading && !resource.data) return <Loading />;
  if (resource.error && !resource.data) return <Alert>{resource.error}</Alert>;
  if (!resource.data) return null;
  const { list, workers } = resource.data;
  const owner = (workerId: string | null) => {
    if (!workerId) return "Organization";
    const worker = workers.find((item) => item.id === workerId);
    return worker ? `${worker.first_name} ${worker.last_name}` : "Team member";
  };

  async function mutate(task: () => Promise<unknown>, message: string) {
    const ok = await action.run(task, message);
    await resource.reload();
    return ok;
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    const { input, errors: problems } = validateQualificationDraft(draft, todayIso());
    setErrors(problems);
    if (!input) return;
    const ok = editing
      ? await mutate(() => api.updateQualification(editing.id, {
          title: input.title,
          issuer: input.issuer,
          jurisdiction: input.jurisdiction,
          reference_last4: input.reference_last4,
          issued_on: input.issued_on,
          expires_on: input.expires_on,
          evidence_reference: input.evidence_reference,
        }, editing.version), "Qualification updated. Submit it again for review.")
      : await mutate(() => api.addQualification(input), "Qualification saved as a draft.");
    if (ok) {
      setEditing(null);
      setDraft(emptyQualificationDraft());
    }
  }

  const set = (patch: Partial<QualificationDraft>) => setDraft({ ...draft, ...patch });

  return (
    <>
      <Alert>{errors.join(" ")}</Alert>
      <Alert>{action.error}</Alert>
      <Alert tone="success">{action.notice}</Alert>
      {!list.evidence_storage.upload_enabled && <Alert tone="info">{list.evidence_storage.reason}</Alert>}

      <Panel title="Licenses, insurance & documents" description="Only the last four characters of any reference number are stored. BREERO reviews each submission.">
        {list.items.length === 0 ? <Empty>No qualifications recorded yet.</Empty> : (
          <div className="portal-table-wrap">
            <table>
              <thead><tr><th>Type</th><th>Title</th><th>Holder</th><th>Expires</th><th>Status</th><th>Reviewer note</th><th><span className="partner-sr">Actions</span></th></tr></thead>
              <tbody>
                {list.items.map((item) => {
                  const view = qualificationStatusView(item);
                  return (
                    <tr key={item.id}>
                      <td>{QUALIFICATION_TYPES.find((type) => type.value === item.qualification_type)?.label}</td>
                      <td>{item.title}{item.jurisdiction ? ` (${item.jurisdiction})` : ""}{item.reference_last4 ? ` ••••${item.reference_last4}` : ""}</td>
                      <td>{owner(item.worker_id)}</td>
                      <td>{formatDate(item.expires_on)}</td>
                      <td><StatusBadge label={view.label} tone={view.tone} /></td>
                      <td>{item.review_reason ?? "—"}</td>
                      <td className="partner-row-actions">
                        {canEditQualification(item) && (
                          <button type="button" className="partner-link" disabled={action.busy} onClick={() => { setEditing(item); setDraft(toDraft(item)); }}>Edit</button>
                        )}
                        {canSubmitQualification(item) && (
                          <button type="button" className="partner-link" disabled={action.busy} onClick={() => void mutate(() => api.submitQualification(item.id, item.version), "Submitted for review.")}>Submit</button>
                        )}
                        <button type="button" className="partner-link" disabled={action.busy} onClick={() => void mutate(() => api.withdrawQualification(item.id, item.version), "Qualification withdrawn.")}>Withdraw</button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel title={editing ? "Edit qualification" : "Add qualification"}>
        <form className="partner-form" onSubmit={(event) => void save(event)}>
          <div className="partner-grid">
            <Field label="Type">
              <select value={draft.qualificationType} disabled={Boolean(editing)} onChange={(e) => set({ qualificationType: e.target.value as QualificationType })}>
                {QUALIFICATION_TYPES.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}
              </select>
            </Field>
            <Field label="Title"><input required maxLength={160} value={draft.title} onChange={(e) => set({ title: e.target.value })} /></Field>
            <Field label="Issuer (optional)"><input maxLength={160} value={draft.issuer} onChange={(e) => set({ issuer: e.target.value })} /></Field>
            <Field label="Jurisdiction (optional)" hint="State or country code, e.g. TX"><input maxLength={3} value={draft.jurisdiction} onChange={(e) => set({ jurisdiction: e.target.value })} /></Field>
            <Field label="Reference — last 4 (optional)"><input maxLength={4} value={draft.referenceLast4} onChange={(e) => set({ referenceLast4: e.target.value })} /></Field>
            <Field label="Issued on (optional)"><input type="date" value={draft.issuedOn} onChange={(e) => set({ issuedOn: e.target.value })} /></Field>
            <Field label="Expires on"><input type="date" value={draft.expiresOn} onChange={(e) => set({ expiresOn: e.target.value })} /></Field>
            <Field label="Evidence reference (optional)" hint="An ID BREERO can match, not a link.">
              <input maxLength={128} value={draft.evidenceReference} onChange={(e) => set({ evidenceReference: e.target.value })} />
            </Field>
            <Field label="Holder">
              <select value={draft.workerId} disabled={Boolean(editing)} onChange={(e) => set({ workerId: e.target.value })}>
                <option value="">Organization</option>
                {workers.map((item) => <option key={item.id} value={item.id}>{item.first_name} {item.last_name}</option>)}
              </select>
            </Field>
          </div>
          <p className="partner-muted">Document upload is unavailable until BREERO enables governed document storage.</p>
          <div className="partner-actions">
            <button type="submit" className="partner-button" disabled={action.busy}>{editing ? "Save changes" : "Save draft"}</button>
            {editing && <button type="button" className="partner-button partner-button--ghost" onClick={() => { setEditing(null); setDraft(emptyQualificationDraft()); }}>Cancel</button>}
          </div>
        </form>
      </Panel>
    </>
  );
}
