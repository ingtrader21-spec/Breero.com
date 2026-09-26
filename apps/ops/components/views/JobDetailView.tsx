import type { ReactNode } from "react";
import { formatDateTime, formatMoney, humanize, locationLabel, shortId, statusLabel } from "../../lib/format";
import type { JobControlDetail } from "../../lib/types";
import { Empty, Panel, RiskList, SeverityBadge, StatusBadge } from "../ui";

export function JobDetailView({ detail, actions }: { detail: JobControlDetail; actions?: ReactNode }) {
  const { job } = detail;
  const zone = job.location.timezone_name;
  return (
    <div className="ops-stack">
      <section className="ops-summary" aria-label="Job summary">
        <div>
          <p className="ops-eyebrow">Job {shortId(job.job_id)} · version {job.version}</p>
          <h2 className="ops-summary__title">{job.service_name ?? "Service"} <StatusBadge status={job.status} /> <SeverityBadge severity={job.highest_severity} /></h2>
          <p className="ops-muted">
            {formatDateTime(job.scheduled_start, zone)} → {formatDateTime(job.scheduled_end, zone)} · {job.location.service_area_name ?? "Unzoned"} · {locationLabel(job.location)}
          </p>
        </div>
        <dl className="ops-facts">
          <div><dt>Vendor</dt><dd>{job.vendor ? job.vendor.name : "—"}</dd></div>
          <div><dt>Worker</dt><dd>{job.worker ? `${job.worker.name}${job.worker.available === false ? " (unavailable)" : ""}` : "Unassigned"}</dd></div>
          <div><dt>Booking</dt><dd>{detail.booking ? `${detail.booking.reference} · ${humanize(detail.booking.status.toLowerCase())}` : "No booking"}</dd></div>
          <div><dt>Live offers</dt><dd>{job.live_offer_count}</dd></div>
        </dl>
      </section>

      <Panel title="SLA findings"><RiskList risks={job.risks} /></Panel>

      {actions}

      <div className="ops-grid-2">
        <Panel title="Timeline">
          {detail.timeline.length === 0 ? <Empty>No recorded events.</Empty> : (
            <ol className="ops-timeline">
              {detail.timeline.map((entry, index) => (
                <li key={`${entry.kind}-${entry.at}-${index}`}>
                  <time dateTime={entry.at}>{formatDateTime(entry.at, zone)}</time>
                  <strong>
                    {entry.kind === "status" && entry.to_status
                      ? entry.action === "reassigned"
                        ? "Reassigned"
                        : `${entry.from_status ? statusLabel(entry.from_status) : "—"} → ${statusLabel(entry.to_status)}`
                      : humanize(entry.action)}
                  </strong>
                  <span className="ops-muted">{entry.actor_type ?? "system"}{entry.reason ? ` · ${entry.reason}` : ""}</span>
                </li>
              ))}
            </ol>
          )}
        </Panel>
        <div className="ops-stack">
          <Panel title="Diagnostics">
            <dl className="ops-facts ops-facts--stacked">
              <div><dt>Diagnostic notes</dt><dd>{detail.diagnostics.diagnostic_notes ?? "Not recorded"}</dd></div>
              <div><dt>Completion notes</dt><dd>{detail.diagnostics.completion_notes ?? "Not recorded"}</dd></div>
              <div><dt>Completed</dt><dd>{formatDateTime(detail.diagnostics.completed_at, zone)}</dd></div>
            </dl>
          </Panel>
          <Panel title="Assignment history">
            {detail.assignments.length === 0 ? <Empty>No assignments yet.</Empty> : (
              <table className="ops-table">
                <thead><tr><th scope="col">Worker</th><th scope="col">Status</th><th scope="col">Assigned</th><th scope="col">Released</th></tr></thead>
                <tbody>
                  {detail.assignments.map((assignment) => (
                    <tr key={assignment.id}>
                      <td className="ops-mono">{shortId(assignment.worker_id)}</td>
                      <td>{humanize(assignment.status.toLowerCase())}</td>
                      <td>{formatDateTime(assignment.assigned_at, zone)}</td>
                      <td>{formatDateTime(assignment.released_at, zone)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>
          <Panel title="Offers">
            {detail.offers.length === 0 ? <Empty>No offers have been created.</Empty> : (
              <table className="ops-table">
                <thead><tr><th scope="col">Round</th><th scope="col">Vendor</th><th scope="col">Status</th><th scope="col" className="ops-num">Score</th><th scope="col">Expires</th></tr></thead>
                <tbody>
                  {detail.offers.map((offer) => (
                    <tr key={offer.id}>
                      <td>{offer.round}</td>
                      <td className="ops-mono">{shortId(offer.vendor_id)}</td>
                      <td>{humanize(offer.status.toLowerCase())}</td>
                      <td className="ops-num">{offer.score}</td>
                      <td>{formatDateTime(offer.expires_at, zone)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>
          <Panel title="Integration deliveries">
            {detail.integration_events.length === 0 ? <Empty>No integration events for this job.</Empty> : (
              <ul className="ops-list">
                {detail.integration_events.map((event) => (
                  <li key={event.id}>
                    <strong>{event.event_type}</strong> · {humanize(event.status.toLowerCase())} · {event.attempt_count} attempts
                    {event.last_error_code && <span className="ops-muted"> · {event.last_error_code}</span>}
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}

export function WorkRequestList({ detail, busy, onReview }: { detail: JobControlDetail; busy: boolean; onReview: (requestId: string, approve: boolean) => void }) {
  const reviewable = new Set(detail.actions.reviewable_work_request_ids);
  return (
    <Panel title="Work requests">
      {detail.work_requests.length === 0 ? <Empty>No additional work has been requested.</Empty> : (
        <ul className="ops-list">
          {detail.work_requests.map((request) => (
            <li key={request.id} className="ops-work-request">
              <div>
                <strong>{formatMoney(request.total_minor, request.currency)}</strong> · {humanize(request.status.toLowerCase())}
                <p>{request.description}</p>
                <span className="ops-muted">Submitted {formatDateTime(request.created_at, detail.job.location.timezone_name)} · {request.line_items.length} line items</span>
              </div>
              {reviewable.has(request.id) && (
                <div className="ops-actions">
                  <button type="button" className="ops-button" disabled={busy} onClick={() => onReview(request.id, true)}>Send to customer</button>
                  <button type="button" className="ops-button ops-button--danger" disabled={busy} onClick={() => onReview(request.id, false)}>Decline</button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
