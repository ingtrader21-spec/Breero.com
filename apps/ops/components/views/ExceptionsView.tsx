import { RISK_LABELS, SEVERITY_LABELS } from "../../lib/format";
import type { ExceptionQueue } from "../../lib/types";
import { Notice, Panel } from "../ui";
import { JobTable } from "./JobTable";

export function ExceptionsView({ data }: { data: ExceptionQueue }) {
  const { policy } = data;
  return (
    <div className="ops-stack">
      <div className="ops-grid-2">
        <Panel title="By severity">
          <ul className="ops-kv">
            {data.by_severity.map((entry) => <li key={entry.severity}><span>{SEVERITY_LABELS[entry.severity]}</span><strong>{entry.count}</strong></li>)}
          </ul>
        </Panel>
        <Panel title="By finding">
          {data.by_code.length === 0 ? <p className="ops-muted">No findings.</p> : (
            <ul className="ops-kv">
              {data.by_code.map((entry) => <li key={entry.code}><span>{RISK_LABELS[entry.code] ?? entry.code}</span><strong>{entry.count}</strong></li>)}
            </ul>
          )}
        </Panel>
      </div>
      <Notice>
        Server policy: unassigned jobs are flagged {policy.unassigned_lead_time_minutes} minutes before start; approvals stall after {policy.approval_stall_after_minutes} minutes; work requests need review within {policy.work_request_review_after_minutes} minutes. Scanned {data.scanned_jobs} active jobs{data.scan_truncated ? " (scan limit reached — earliest-scheduled jobs only)" : ""}.
      </Notice>
      <Panel title="Exception queue">
        <JobTable items={data.items} generatedAt={data.generated_at} emptyMessage="No active job currently breaches the operations policy." />
      </Panel>
    </div>
  );
}
