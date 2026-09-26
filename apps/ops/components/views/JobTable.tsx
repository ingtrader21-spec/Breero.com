import Link from "next/link";
import { formatDateTime, locationLabel, relativeTo } from "../../lib/format";
import type { QueueItem } from "../../lib/types";
import { Empty, RiskList, SeverityBadge, StatusBadge } from "../ui";

export function JobTable({ items, generatedAt, emptyMessage }: { items: QueueItem[]; generatedAt: string; emptyMessage: string }) {
  if (items.length === 0) return <Empty>{emptyMessage}</Empty>;
  return (
    <div className="ops-table-wrap">
      <table className="ops-table">
        <thead>
          <tr>
            <th scope="col">Job</th>
            <th scope="col">Status</th>
            <th scope="col">Risk</th>
            <th scope="col">Scheduled</th>
            <th scope="col">Service</th>
            <th scope="col">Area</th>
            <th scope="col">Assigned</th>
            <th scope="col" className="ops-num">Offers</th>
            <th scope="col" className="ops-num">Reviews</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.job_id} className={item.highest_severity ? `ops-row--${item.highest_severity.toLowerCase()}` : undefined}>
              <td><Link href={`/jobs/${item.job_id}`} className="ops-mono">{item.job_id.slice(0, 8)}</Link></td>
              <td><StatusBadge status={item.status} /></td>
              <td><SeverityBadge severity={item.highest_severity} /><RiskList risks={item.risks} /></td>
              <td>
                {formatDateTime(item.scheduled_start, item.location.timezone_name)}
                <span className="ops-muted ops-block">{relativeTo(item.scheduled_start, generatedAt)}</span>
              </td>
              <td>{item.service_name ?? "—"}</td>
              <td>{item.location.service_area_name ?? "Unzoned"}<span className="ops-muted ops-block">{locationLabel(item.location)}</span></td>
              <td>
                {item.worker ? item.worker.name : <span className="ops-muted">Unassigned</span>}
                {item.vendor && <span className="ops-muted ops-block">{item.vendor.name}</span>}
              </td>
              <td className="ops-num">{item.live_offer_count}</td>
              <td className="ops-num">{item.unreviewed_work_request_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
