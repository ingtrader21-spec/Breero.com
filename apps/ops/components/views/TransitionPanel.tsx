"use client";

import { useState, type FormEvent } from "react";
import { STATUS_LABELS, TECHNICIAN_COMMAND_LABELS } from "../../lib/format";
import type { JobStatus } from "../../lib/types";
import { Notice, Panel } from "../ui";

export interface TransitionPanelProps {
  allowed: JobStatus[];
  technicianCommands: string[];
  busy: boolean;
  onTransition: (status: JobStatus, reason: string) => void;
}

export function TransitionPanel({ allowed, technicianCommands, busy, onTransition }: TransitionPanelProps) {
  const [target, setTarget] = useState<JobStatus | "">("");
  const [reason, setReason] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const destructive = target === "CANCELLED";
  const canSubmit = Boolean(target) && allowed.includes(target as JobStatus) && Boolean(reason.trim()) && (!destructive || confirmed) && !busy;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!canSubmit || !target) return;
    // Inputs are kept on failure; the page remounts this panel when the job version changes.
    onTransition(target, reason.trim());
  }

  return (
    <Panel title="Lifecycle">
      {technicianCommands.length > 0 && (
        <p className="ops-muted">Technician app next steps: {technicianCommands.map((command) => TECHNICIAN_COMMAND_LABELS[command] ?? command).join(", ")}.</p>
      )}
      {allowed.length === 0 ? <Notice>This job is in a terminal state; no transitions are permitted.</Notice> : (
        <form onSubmit={submit} className="ops-inline-form" aria-label="Transition job">
          <label>Move to
            <select value={target} onChange={(event) => { setTarget(event.target.value as JobStatus | ""); setConfirmed(false); }}>
              <option value="">Select a permitted status</option>
              {allowed.map((status) => <option key={status} value={status}>{STATUS_LABELS[status]}</option>)}
            </select>
          </label>
          <label className="ops-grow">Reason
            <input required maxLength={1000} value={reason} onChange={(event) => setReason(event.target.value)} />
          </label>
          {destructive && (
            <label className="ops-chip ops-chip--danger">
              <input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />
              Confirm cancellation
            </label>
          )}
          <button type="submit" className={`ops-button${destructive ? " ops-button--danger" : ""}`} disabled={!canSubmit}>Apply</button>
        </form>
      )}
    </Panel>
  );
}
