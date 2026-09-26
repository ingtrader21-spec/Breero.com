import { formatDateTime } from "../../lib/format";
import type { CapacityBoard } from "../../lib/types";
import { Empty, Notice, Panel, Stat } from "../ui";

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export function CapacityView({ data }: { data: CapacityBoard }) {
  const { totals } = data;
  return (
    <div className="ops-stack">
      <div className="ops-stats" aria-label="Capacity totals">
        <Stat label="Workers" value={totals.workers} />
        <Stat label="Daily capacity" value={totals.daily_capacity} />
        <Stat label="Jobs in window" value={totals.jobs_in_window} />
        <Stat label="Over capacity" value={totals.workers_over_capacity} tone={totals.workers_over_capacity ? "alert" : "ok"} />
        <Stat label="No hours configured" value={totals.workers_without_hours} tone={totals.workers_without_hours ? "warn" : "ok"} />
      </div>
      <Notice>
        {WEEKDAYS[data.weekday]} working hours; jobs counted by scheduled start between {formatDateTime(data.window_start)} and {formatDateTime(data.window_end)}.
        {data.truncated ? " Worker list truncated at the server limit." : ""}
      </Notice>
      <Panel title="Workload by worker">
        {data.workers.length === 0 ? <Empty>No workers match this view.</Empty> : (
          <div className="ops-table-wrap">
            <table className="ops-table">
              <thead>
                <tr>
                  <th scope="col">Worker</th>
                  <th scope="col">Vendor</th>
                  <th scope="col">Shift</th>
                  <th scope="col" className="ops-num">Capacity</th>
                  <th scope="col" className="ops-num">In window</th>
                  <th scope="col">Utilization</th>
                  <th scope="col" className="ops-num">Active jobs</th>
                  <th scope="col" className="ops-num">ZIPs / services</th>
                </tr>
              </thead>
              <tbody>
                {data.workers.map((worker) => (
                  <tr key={worker.worker_id} className={worker.over_capacity ? "ops-row--critical" : undefined}>
                    <td>{worker.worker_name}{!worker.available && <span className="ops-tag">Unavailable</span>}</td>
                    <td>{worker.vendor_name}</td>
                    <td>{worker.shift_start && worker.shift_end ? `${worker.shift_start}–${worker.shift_end}` : <span className="ops-muted">No hours</span>}</td>
                    <td className="ops-num">{worker.daily_capacity}</td>
                    <td className="ops-num">{worker.jobs_in_window}</td>
                    <td>
                      {worker.utilization_percent === null ? <span className="ops-muted">—</span> : (
                        <span className="ops-meter" title={`${worker.worker_name} utilization`}>
                          <span className="ops-meter__bar" style={{ width: `${Math.min(worker.utilization_percent, 100)}%` }} />
                          <span className="ops-meter__label">{worker.utilization_percent}%</span>
                        </span>
                      )}
                      {worker.over_capacity && <span className="ops-tag ops-tag--alert">Over capacity</span>}
                    </td>
                    <td className="ops-num">{worker.active_jobs}</td>
                    <td className="ops-num">{worker.covered_postal_codes} / {worker.covered_services}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}
