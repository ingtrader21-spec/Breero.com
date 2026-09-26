import Link from "next/link";
import { formatDateTime, humanize, shortId } from "../../lib/format";
import type { IntegrationFailurePage } from "../../lib/types";
import { Empty, Notice, Panel } from "../ui";

export function IntegrationFailuresView({ data }: { data: IntegrationFailurePage }) {
  return (
    <div className="ops-stack">
      <Notice>
        Payloads and raw provider errors are withheld from this view.{" "}
        {data.retry_permitted
          ? "Your account may retry deliveries from the Admin portal integration console."
          : "Retrying a delivery requires a finance or admin account."}
      </Notice>
      <Panel title="Failed deliveries">
        {data.items.length === 0 ? <Empty>No failed integration deliveries.</Empty> : (
          <div className="ops-table-wrap">
            <table className="ops-table">
              <thead>
                <tr>
                  <th scope="col">Event</th>
                  <th scope="col">Aggregate</th>
                  <th scope="col">Status</th>
                  <th scope="col" className="ops-num">Attempts</th>
                  <th scope="col">Error code</th>
                  <th scope="col">Last error</th>
                  <th scope="col">Created</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((event) => (
                  <tr key={event.id}>
                    <td>{event.event_type}</td>
                    <td>
                      {event.aggregate_type === "job"
                        ? <Link href={`/jobs/${event.aggregate_id}`} className="ops-mono">job {shortId(event.aggregate_id)}</Link>
                        : <span className="ops-mono">{event.aggregate_type} {shortId(event.aggregate_id)}</span>}
                    </td>
                    <td>{humanize(event.status.toLowerCase())}</td>
                    <td className="ops-num">{event.attempt_count}</td>
                    <td className="ops-mono">{event.last_error_code ?? "—"}</td>
                    <td>{formatDateTime(event.last_error_at)}</td>
                    <td>{formatDateTime(event.created_at)}</td>
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
