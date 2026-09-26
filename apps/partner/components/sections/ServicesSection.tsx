"use client";

import { useCallback, useState } from "react";

import { labelize } from "../../lib/format";
import type { ApprovalStatus } from "../../lib/types";
import type { SectionProps } from "../PartnerApp";
import { Alert, Empty, Field, Loading, Panel, StatusBadge, useAction, useResource } from "../ui";

export const approvalTone = (status: ApprovalStatus) =>
  status === "APPROVED" ? "success" : status === "REJECTED" ? "danger" : "info";

export function ServicesSection({ api }: SectionProps) {
  const load = useCallback(async () => {
    const [selected, catalog] = await Promise.all([api.services(true), api.catalogServices()]);
    return { selected: selected.items, catalog: catalog.filter((item) => item.is_active) };
  }, [api]);
  const resource = useResource(load);
  const action = useAction();
  const [choice, setChoice] = useState("");

  if (resource.loading && !resource.data) return <Loading />;
  if (resource.error && !resource.data) return <Alert>{resource.error}</Alert>;
  if (!resource.data) return null;
  const { selected, catalog } = resource.data;
  const activeIds = new Set(selected.filter((item) => item.active).map((item) => item.service_id));
  const available = catalog.filter((item) => !activeIds.has(item.id));

  async function mutate(task: () => Promise<unknown>, message: string) {
    await action.run(task, message);
    await resource.reload();
  }

  return (
    <>
      <Alert>{action.error}</Alert>
      <Alert tone="success">{action.notice}</Alert>
      <Panel title="Services you offer" description="Selections come from the BREERO catalog and are reviewed before jobs are offered. Selections lock while your application is under review.">
        {selected.length === 0 ? (
          <Empty>No services selected yet.</Empty>
        ) : (
          <div className="portal-table-wrap">
            <table>
              <thead><tr><th>Service</th><th>Category</th><th>Review</th><th>Required skills</th><th>State</th><th><span className="partner-sr">Actions</span></th></tr></thead>
              <tbody>
                {selected.map((item) => (
                  <tr key={item.id}>
                    <td>{item.service_name}</td>
                    <td>{labelize(item.service_category)}</td>
                    <td><StatusBadge label={labelize(item.status)} tone={approvalTone(item.status)} /></td>
                    <td>{item.required_skills.map((skill) => skill.name).join(", ") || "—"}</td>
                    <td>{item.active ? "Offered" : "Withdrawn"}</td>
                    <td>
                      {item.active ? (
                        <button type="button" className="partner-link" disabled={action.busy} onClick={() => void mutate(() => api.removeService(item.id, item.version), `${item.service_name} withdrawn.`)}>Withdraw</button>
                      ) : (
                        <button type="button" className="partner-link" disabled={action.busy} onClick={() => void mutate(() => api.updateService(item.id, { active: true }, item.version), `${item.service_name} re-offered.`)}>Offer again</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
      <Panel title="Add a service">
        {available.length === 0 ? (
          <Empty>Every active catalog service is already selected.</Empty>
        ) : (
          <form
            className="partner-inline-form"
            onSubmit={(event) => {
              event.preventDefault();
              if (choice) void mutate(() => api.addService(choice), "Service added.").then(() => setChoice(""));
            }}
          >
            <Field label="Catalog service">
              <select value={choice} onChange={(e) => setChoice(e.target.value)} required>
                <option value="">Select a service…</option>
                {available.map((item) => <option key={item.id} value={item.id}>{item.name} — {labelize(item.category)}</option>)}
              </select>
            </Field>
            <button type="submit" className="partner-button" disabled={action.busy || !choice}>Add service</button>
          </form>
        )}
      </Panel>
    </>
  );
}
