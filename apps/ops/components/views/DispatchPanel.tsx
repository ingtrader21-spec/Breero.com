"use client";

import { useState, type FormEvent } from "react";
import { BLOCKING_REASON_LABELS } from "../../lib/format";
import type { AssignmentCandidate, AssignmentCandidates, JobActions } from "../../lib/types";
import { Empty, ErrorBanner, Notice, Panel } from "../ui";

export interface DispatchPanelProps {
  actions: JobActions;
  candidates?: AssignmentCandidates;
  candidatesError?: string;
  busy: boolean;
  onMatch: () => void;
  onAssign: (candidate: AssignmentCandidate, reason: string) => void;
  onReassign: (candidate: AssignmentCandidate, reason: string, expectedVersion: number) => void;
}

export function DispatchPanel({ actions, candidates, candidatesError, busy, onMatch, onAssign, onReassign }: DispatchPanelProps) {
  const [selected, setSelected] = useState("");
  const [reason, setReason] = useState("");
  const mode = candidates?.mode ?? "none";
  const choice = candidates?.candidates.find((candidate) => candidate.worker_id === selected && candidate.eligible);
  const canSubmit = Boolean(choice && reason.trim()) && !busy && (mode === "assign" ? actions.can_assign : mode === "reassign" ? actions.can_reassign : false);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!choice || !candidates || !canSubmit) return;
    // Inputs are kept on failure; the page remounts this panel when the job version changes.
    if (mode === "assign") onAssign(choice, reason.trim());
    else onReassign(choice, reason.trim(), candidates.job_version);
  }

  if (!actions.can_match && !actions.can_assign && !actions.can_reassign) {
    return <Panel title="Dispatch"><Notice>Dispatch changes are not permitted in the job&apos;s current state.</Notice></Panel>;
  }

  return (
    <Panel
      title={mode === "reassign" ? "Reassign" : "Match & assign"}
      actions={actions.can_match ? <button type="button" className="ops-button ops-button--ghost" disabled={busy} onClick={onMatch}>Run matching</button> : undefined}
    >
      {candidatesError && <ErrorBanner message={candidatesError} />}
      {candidates && (
        <form onSubmit={submit} className="ops-stack" aria-label={mode === "reassign" ? "Reassign job" : "Assign job"}>
          {mode === "reassign" && <Notice>Reassignment is only possible before travel starts. The server re-checks coverage, hours, credentials and capacity and moves the reserved booking slot.</Notice>}
          {candidates.candidates.length === 0 ? <Empty>No active workers are available to pre-screen.</Empty> : (
            <div className="ops-table-wrap">
              <table className="ops-table">
                <thead>
                  <tr>
                    <th scope="col"><span className="ops-sr-only">Select</span></th>
                    <th scope="col">Worker</th>
                    <th scope="col">Vendor</th>
                    <th scope="col">Coverage</th>
                    <th scope="col" className="ops-num">Active jobs</th>
                    <th scope="col">Eligibility</th>
                  </tr>
                </thead>
                <tbody>
                  {candidates.candidates.map((candidate) => (
                    <tr key={candidate.worker_id} className={candidate.eligible ? undefined : "ops-row--disabled"}>
                      <td>
                        <input
                          type="radio"
                          name="candidate"
                          value={candidate.worker_id}
                          aria-label={`Select ${candidate.worker_name}`}
                          disabled={!candidate.eligible || busy}
                          checked={selected === candidate.worker_id}
                          onChange={() => setSelected(candidate.worker_id)}
                        />
                      </td>
                      <td>{candidate.worker_name}{candidate.holds_reserved_slot && <span className="ops-tag">Reserved slot</span>}</td>
                      <td>{candidate.vendor_name}</td>
                      <td>{candidate.covers_job_postal_code ? "Covers ZIP" : <span className="ops-muted">No ZIP coverage</span>}</td>
                      <td className="ops-num">{candidate.active_jobs}</td>
                      <td>
                        {candidate.eligible ? "Eligible" : (
                          <ul className="ops-reasons">{candidate.blocking_reasons.map((code) => <li key={code}>{BLOCKING_REASON_LABELS[code] ?? code}</li>)}</ul>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <label className="ops-field">Reason (recorded in the audit log)
            <textarea required maxLength={1000} value={reason} onChange={(event) => setReason(event.target.value)} rows={2} />
          </label>
          <div className="ops-actions">
            <button type="submit" className="ops-button" disabled={!canSubmit}>{mode === "reassign" ? "Reassign job" : "Assign job"}</button>
          </div>
        </form>
      )}
    </Panel>
  );
}
