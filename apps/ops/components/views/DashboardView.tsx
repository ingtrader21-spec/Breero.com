import Link from "next/link";
import { SEVERITY_LABELS, statusLabel } from "../../lib/format";
import type { OperationsDashboard } from "../../lib/types";
import { Notice, Panel, Stat } from "../ui";

export function DashboardView({ data }: { data: OperationsDashboard }) {
  const critical = data.risk_by_severity.find((item) => item.severity === "CRITICAL")?.count ?? 0;
  return (
    <div className="ops-stack">
      <div className="ops-stats" aria-label="Operations summary">
        <Stat label="Active jobs" value={data.active_jobs} />
        <Stat label="Unassigned" value={data.unassigned_jobs} tone={data.unassigned_jobs ? "warn" : "ok"} />
        <Stat label="At risk" value={data.at_risk_jobs} tone={critical ? "alert" : data.at_risk_jobs ? "warn" : "ok"} hint={critical ? `${critical} critical` : undefined} />
        <Stat label="Starting in 24h" value={data.scheduled_next_24h} />
        <Stat label="Live offers" value={data.live_offers} />
        <Stat label="Work requests to review" value={data.work_requests_awaiting_review} tone={data.work_requests_awaiting_review ? "warn" : "ok"} />
        <Stat label="Awaiting customer" value={data.work_requests_awaiting_customer} />
        <Stat label="Integration failures" value={data.integrations.failed} tone={data.integrations.failed ? "alert" : "ok"} hint={data.integrations.retrying ? `${data.integrations.retrying} retrying` : undefined} />
      </div>
      {data.risk_scan_truncated && <Notice>Risk counts cover the earliest-scheduled active jobs only; the scan limit was reached.</Notice>}
      <div className="ops-grid-2">
        <Panel title="Jobs by status" actions={<Link className="ops-link" href="/queue">Open dispatch queue</Link>}>
          <table className="ops-table">
            <thead><tr><th scope="col">Status</th><th scope="col" className="ops-num">Jobs</th></tr></thead>
            <tbody>
              {data.jobs_by_status.map((entry) => (
                <tr key={entry.status}>
                  <td><Link href={`/queue?status=${entry.status}`}>{statusLabel(entry.status)}</Link></td>
                  <td className="ops-num">{entry.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
        <div className="ops-stack">
          <Panel title="SLA exceptions" actions={<Link className="ops-link" href="/exceptions">Open exception queue</Link>}>
            <ul className="ops-kv">
              {data.risk_by_severity.map((entry) => (
                <li key={entry.severity}><span>{SEVERITY_LABELS[entry.severity]}</span><strong>{entry.count}</strong></li>
              ))}
            </ul>
          </Panel>
          <Panel title="Workforce" actions={<Link className="ops-link" href="/capacity">Open capacity</Link>}>
            <ul className="ops-kv">
              <li><span>Active vendors</span><strong>{data.workforce.active_vendors}</strong></li>
              <li><span>Active workers</span><strong>{data.workforce.active_workers}</strong></li>
              <li><span>Dispatchable now</span><strong>{data.workforce.dispatchable_workers}</strong></li>
            </ul>
          </Panel>
        </div>
      </div>
    </div>
  );
}
