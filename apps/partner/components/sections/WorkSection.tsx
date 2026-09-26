"use client";

import { useCallback, useState } from "react";

import { ApiError } from "../../lib/api";
import { formatDateTime, labelize } from "../../lib/format";
import type { JobStatus, OfferStatus, ProfessionalLead } from "../../lib/types";
import type { SectionProps } from "../PartnerApp";
import { Alert, Empty, Field, Loading, Panel, StatusBadge, useAction, useResource } from "../ui";

export function jobTone(status: JobStatus) {
  if (status === "COMPLETED") return "success" as const;
  if (status === "CANCELLED") return "danger" as const;
  if (status === "OFFERED" || status === "MATCHING" || status === "CREATED") return "info" as const;
  return "warning" as const;
}

export function offerTone(status: OfferStatus) {
  if (status === "ACCEPTED") return "success" as const;
  if (status === "PENDING") return "info" as const;
  return "neutral" as const;
}

export function isOfferActionable(offer: { status: OfferStatus; expires_at: string }, now: number = Date.now()): boolean {
  return offer.status === "PENDING" && Date.parse(offer.expires_at) > now;
}

async function optionalLeads(load: () => Promise<ProfessionalLead[]>): Promise<ProfessionalLead[] | null> {
  try {
    return await load();
  } catch (reason) {
    if (reason instanceof ApiError && (reason.status === 404 || reason.status === 403)) return null;
    throw reason;
  }
}

export function WorkSection({ api }: SectionProps) {
  const load = useCallback(async () => {
    const [offers, jobs, workers, leads] = await Promise.all([
      api.offers(),
      api.jobs(),
      api.workers(),
      optionalLeads(() => api.leads()),
    ]);
    return { offers: offers.items, jobs: jobs.items, workers: workers.items, leads };
  }, [api]);
  const resource = useResource(load);
  const action = useAction();
  const [assignee, setAssignee] = useState<Record<string, string>>({});

  if (resource.loading && !resource.data) return <Loading />;
  if (resource.error && !resource.data) return <Alert>{resource.error}</Alert>;
  if (!resource.data) return null;
  const { offers, jobs, workers, leads } = resource.data;
  const dispatchable = workers.filter((item) => item.available && item.status === "ACTIVE");
  const workerName = (id: string | null) => {
    if (!id) return "Unassigned";
    const worker = workers.find((item) => item.id === id);
    return worker ? `${worker.first_name} ${worker.last_name}` : "Team member";
  };

  async function decide(offerId: string, accept: boolean, workerId?: string) {
    await action.run(
      () => api.decideOffer(offerId, accept, workerId),
      accept ? "Offer accepted." : "Offer declined.",
    );
    await resource.reload();
  }

  return (
    <>
      <Alert>{action.error}</Alert>
      <Alert tone="success">{action.notice}</Alert>
      <Panel title="Job offers" description="Offers BREERO dispatch has sent to your organization. Accepting assigns the selected professional.">
        {offers.length === 0 ? <Empty>No offers yet.</Empty> : (
          <div className="portal-table-wrap">
            <table>
              <thead><tr><th>Service</th><th>Scheduled</th><th>Offer</th><th>Expires</th><th>Professional</th><th><span className="partner-sr">Actions</span></th></tr></thead>
              <tbody>
                {offers.map((offer) => {
                  const actionable = isOfferActionable(offer);
                  const selected = assignee[offer.id] ?? offer.worker_id ?? "";
                  return (
                    <tr key={offer.id}>
                      <td>{offer.service_name ?? "Service"}</td>
                      <td>{formatDateTime(offer.scheduled_start)}</td>
                      <td><StatusBadge label={labelize(offer.status)} tone={offerTone(offer.status)} /></td>
                      <td>{formatDateTime(offer.expires_at)}</td>
                      <td>
                        {actionable ? (
                          <Field label="Assign">
                            <select value={selected} onChange={(e) => setAssignee({ ...assignee, [offer.id]: e.target.value })}>
                              <option value="">Select…</option>
                              {dispatchable.map((item) => <option key={item.id} value={item.id}>{item.first_name} {item.last_name}</option>)}
                            </select>
                          </Field>
                        ) : workerName(offer.worker_id)}
                      </td>
                      <td className="partner-row-actions">
                        {actionable && (
                          <>
                            <button type="button" className="partner-link" disabled={action.busy || !selected} onClick={() => void decide(offer.id, true, selected)}>Accept</button>
                            <button type="button" className="partner-link" disabled={action.busy} onClick={() => void decide(offer.id, false)}>Decline</button>
                          </>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel title="Jobs" description="Jobs assigned to your organization and their live status.">
        {jobs.length === 0 ? <Empty>No jobs assigned yet.</Empty> : (
          <div className="portal-table-wrap">
            <table>
              <thead><tr><th>Service</th><th>Scheduled</th><th>Status</th><th>Professional</th><th>Completed</th></tr></thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.id}>
                    <td>{job.service_name ?? "Service"}</td>
                    <td>{formatDateTime(job.scheduled_start)} – {formatDateTime(job.scheduled_end)}</td>
                    <td><StatusBadge label={labelize(job.status)} tone={jobTone(job.status)} /></td>
                    <td>{workerName(job.worker_id)}</td>
                    <td>{formatDateTime(job.completed_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel title="Professional leads" description="Purchasing access does not guarantee a completed job, sale, contract, appointment outcome, or revenue.">
        {leads === null ? <Empty>Professional leads are not enabled for this environment.</Empty> : leads.length === 0 ? <Empty>No eligible leads right now.</Empty> : (
          <ul className="partner-list">
            {leads.map((lead) => (
              <li key={lead.id}>{labelize(lead.service_category)} · {lead.location_summary} · {labelize(lead.status)} · expires {formatDateTime(lead.expires_at)}</li>
            ))}
          </ul>
        )}
      </Panel>
    </>
  );
}
