"use client";

import { useCallback, useState } from "react";

import { labelize } from "../../lib/format";
import type { SectionProps } from "../PartnerApp";
import { Alert, Empty, Field, Loading, Panel, StatusBadge, useAction, useResource } from "../ui";
import { approvalTone } from "./ServicesSection";

export function SkillsSection({ api }: SectionProps) {
  const load = useCallback(async () => {
    const [skills, catalog, workers] = await Promise.all([api.skills(), api.skillCatalog(), api.workers()]);
    return { skills: skills.items, catalog: catalog.items, workers: workers.items };
  }, [api]);
  const resource = useResource(load);
  const action = useAction();
  const [skillId, setSkillId] = useState("");
  const [workerId, setWorkerId] = useState("");

  if (resource.loading && !resource.data) return <Loading />;
  if (resource.error && !resource.data) return <Alert>{resource.error}</Alert>;
  if (!resource.data) return null;
  const { skills, catalog, workers } = resource.data;
  const workerName = (id: string) => {
    const worker = workers.find((item) => item.id === id);
    return worker ? `${worker.first_name} ${worker.last_name}`.trim() : "Team member";
  };

  async function mutate(task: () => Promise<unknown>, message: string) {
    const ok = await action.run(task, message);
    await resource.reload();
    return ok;
  }

  return (
    <>
      <Alert>{action.error}</Alert>
      <Alert tone="success">{action.notice}</Alert>
      <Panel title="Professional skills" description="Skills are chosen from the BREERO skill catalog per team member and reviewed before dispatch relies on them.">
        {skills.length === 0 ? (
          <Empty>No skills recorded yet.</Empty>
        ) : (
          <div className="portal-table-wrap">
            <table>
              <thead><tr><th>Professional</th><th>Skill</th><th>Category</th><th>Review</th><th><span className="partner-sr">Actions</span></th></tr></thead>
              <tbody>
                {skills.map((item) => (
                  <tr key={item.id}>
                    <td>{workerName(item.worker_id)}</td>
                    <td>{item.skill.name}</td>
                    <td>{labelize(item.skill.category)}</td>
                    <td><StatusBadge label={labelize(item.status)} tone={approvalTone(item.status)} /></td>
                    <td>
                      <button type="button" className="partner-link" disabled={action.busy} onClick={() => void mutate(() => api.removeSkill(item.id, item.version), `${item.skill.name} removed.`)}>Remove</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
      <Panel title="Add a skill">
        {catalog.length === 0 ? (
          <Empty>The BREERO skill catalog is empty.</Empty>
        ) : (
          <form
            className="partner-inline-form"
            onSubmit={(event) => {
              event.preventDefault();
              if (!skillId) return;
              void mutate(() => api.addSkill(skillId, workerId || undefined), "Skill added.").then((ok) => {
                if (ok) setSkillId("");
              });
            }}
          >
            <Field label="Skill">
              <select value={skillId} onChange={(e) => setSkillId(e.target.value)} required>
                <option value="">Select a skill…</option>
                {catalog.map((item) => <option key={item.id} value={item.id}>{item.name} — {labelize(item.category)}</option>)}
              </select>
            </Field>
            <Field label="Professional" hint="Defaults to you as the account owner.">
              <select value={workerId} onChange={(e) => setWorkerId(e.target.value)}>
                <option value="">Me (account owner)</option>
                {workers.filter((item) => !item.is_account_owner).map((item) => (
                  <option key={item.id} value={item.id}>{item.first_name} {item.last_name}</option>
                ))}
              </select>
            </Field>
            <button type="submit" className="partner-button" disabled={action.busy || !skillId}>Add skill</button>
          </form>
        )}
      </Panel>
    </>
  );
}
