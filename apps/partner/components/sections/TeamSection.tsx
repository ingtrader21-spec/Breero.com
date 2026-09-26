"use client";

import { type FormEvent, useCallback, useState } from "react";

import { labelize } from "../../lib/format";
import type { ProviderWorkerInput } from "../../lib/types";
import type { SectionProps } from "../PartnerApp";
import { Alert, Empty, Field, Loading, Panel, StatusBadge, useAction, useResource } from "../ui";

const EMPTY: ProviderWorkerInput = { first_name: "", last_name: "", email: "", phone: "" };

export function validateWorker(input: ProviderWorkerInput): string[] {
  const errors: string[] = [];
  if (!input.first_name.trim() || !input.last_name.trim()) errors.push("First and last name are required.");
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(input.email.trim())) errors.push("Enter a valid email address.");
  if (input.phone.trim().length < 5) errors.push("Enter a reachable phone number.");
  return errors;
}

export function TeamSection({ api }: SectionProps) {
  const load = useCallback(() => api.workers(), [api]);
  const resource = useResource(load);
  const action = useAction();
  const [draft, setDraft] = useState<ProviderWorkerInput>(EMPTY);
  const [errors, setErrors] = useState<string[]>([]);

  if (resource.loading && !resource.data) return <Loading />;
  if (resource.error && !resource.data) return <Alert>{resource.error}</Alert>;
  if (!resource.data) return null;
  const workers = resource.data.items;

  async function add(event: FormEvent) {
    event.preventDefault();
    const problems = validateWorker(draft);
    setErrors(problems);
    if (problems.length) return;
    const ok = await action.run(
      () => api.addWorker({ ...draft, email: draft.email.trim().toLowerCase() }),
      "Team member added. BREERO operations activates new professionals after review.",
    );
    if (ok) setDraft(EMPTY);
    await resource.reload();
  }

  const bind = (key: keyof ProviderWorkerInput) => ({
    value: draft[key],
    onChange: (event: { target: { value: string } }) => setDraft({ ...draft, [key]: event.target.value }),
  });

  return (
    <>
      <Alert>{action.error}</Alert>
      <Alert tone="success">{action.notice}</Alert>
      <Panel title="Your team" description="Only professionals in your organization are listed. Account linking and dispatch activation are handled by BREERO.">
        {workers.length === 0 ? (
          <Empty>No team members recorded.</Empty>
        ) : (
          <div className="portal-table-wrap">
            <table>
              <thead><tr><th>Name</th><th>Email</th><th>Phone</th><th>Status</th><th>Dispatchable</th><th>Account</th></tr></thead>
              <tbody>
                {workers.map((item) => (
                  <tr key={item.id}>
                    <td>{item.first_name} {item.last_name}{item.is_account_owner ? " (owner)" : ""}</td>
                    <td>{item.email}</td>
                    <td>{item.phone}</td>
                    <td><StatusBadge label={labelize(item.status)} tone={item.status === "ACTIVE" ? "success" : item.status === "INVITED" ? "info" : "neutral"} /></td>
                    <td>{item.available ? "Yes" : "No"}</td>
                    <td>{item.has_account ? "Linked" : "Not linked"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
      <Panel title="Add a team member" description="No invitation is sent automatically.">
        <Alert>{errors.join(" ")}</Alert>
        <form className="partner-form" onSubmit={(event) => void add(event)}>
          <div className="partner-grid">
            <Field label="First name"><input required autoComplete="off" {...bind("first_name")} /></Field>
            <Field label="Last name"><input required autoComplete="off" {...bind("last_name")} /></Field>
            <Field label="Email"><input type="email" required autoComplete="off" {...bind("email")} /></Field>
            <Field label="Phone"><input type="tel" required autoComplete="off" {...bind("phone")} /></Field>
          </div>
          <div className="partner-actions"><button type="submit" className="partner-button" disabled={action.busy}>Add team member</button></div>
        </form>
      </Panel>
    </>
  );
}
