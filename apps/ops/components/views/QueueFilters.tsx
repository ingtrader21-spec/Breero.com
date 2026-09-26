"use client";

import { useState, type FormEvent } from "react";
import { SEVERITY_LABELS, STATUS_LABELS } from "../../lib/format";
import { DEFAULT_QUEUE_FILTERS, queueFilterErrors, type QueueFilterState } from "../../lib/queue-filters";
import { JOB_STATUSES, RISK_SEVERITIES, type JobStatus, type RiskSeverity } from "../../lib/types";

export function QueueFilters({ initial, onApply }: { initial: QueueFilterState; onApply: (filters: QueueFilterState) => void }) {
  const [draft, setDraft] = useState<QueueFilterState>(initial);
  const [errors, setErrors] = useState<string[]>([]);

  function update<K extends keyof QueueFilterState>(key: K, value: QueueFilterState[K]) {
    setDraft((previous) => ({ ...previous, [key]: value }));
  }

  function toggleStatus(status: JobStatus) {
    setDraft((previous) => ({
      ...previous,
      statuses: previous.statuses.includes(status) ? previous.statuses.filter((item) => item !== status) : [...previous.statuses, status],
    }));
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    const problems = queueFilterErrors(draft);
    setErrors(problems);
    if (problems.length === 0) onApply({ ...draft, offset: 0 });
  }

  function reset() {
    setDraft(DEFAULT_QUEUE_FILTERS);
    setErrors([]);
    onApply(DEFAULT_QUEUE_FILTERS);
  }

  return (
    <form className="ops-filters" onSubmit={submit} aria-label="Dispatch queue filters">
      <fieldset className="ops-filters__statuses">
        <legend>Status (default: all active)</legend>
        {JOB_STATUSES.map((status) => (
          <label key={status} className="ops-chip">
            <input type="checkbox" checked={draft.statuses.includes(status)} onChange={() => toggleStatus(status)} />
            {STATUS_LABELS[status]}
          </label>
        ))}
      </fieldset>
      <div className="ops-filters__row">
        <label>Severity
          <select value={draft.severity} onChange={(event) => update("severity", event.target.value as RiskSeverity | "")}>
            <option value="">Any</option>
            {RISK_SEVERITIES.map((severity) => <option key={severity} value={severity}>{SEVERITY_LABELS[severity]}</option>)}
          </select>
        </label>
        <label>Scheduled from<input type="datetime-local" value={draft.scheduledFrom} onChange={(event) => update("scheduledFrom", event.target.value)} /></label>
        <label>Scheduled to<input type="datetime-local" value={draft.scheduledTo} onChange={(event) => update("scheduledTo", event.target.value)} /></label>
        <label>Vendor ID<input value={draft.vendorId} onChange={(event) => update("vendorId", event.target.value)} placeholder="UUID" spellCheck={false} /></label>
        <label>Worker ID<input value={draft.workerId} onChange={(event) => update("workerId", event.target.value)} placeholder="UUID" spellCheck={false} /></label>
        <label>Service area ID<input value={draft.serviceAreaId} onChange={(event) => update("serviceAreaId", event.target.value)} placeholder="UUID" spellCheck={false} /></label>
      </div>
      <div className="ops-filters__row">
        <label className="ops-chip"><input type="checkbox" checked={draft.unassignedOnly} onChange={(event) => update("unassignedOnly", event.target.checked)} />Unassigned only</label>
        <label className="ops-chip"><input type="checkbox" checked={draft.atRiskOnly} onChange={(event) => update("atRiskOnly", event.target.checked)} />At risk only</label>
        <span className="ops-spacer" />
        <button type="button" className="ops-button ops-button--ghost" onClick={reset}>Reset</button>
        <button type="submit" className="ops-button">Apply filters</button>
      </div>
      {errors.length > 0 && <ul className="ops-error" role="alert">{errors.map((error) => <li key={error}>{error}</li>)}</ul>}
    </form>
  );
}
