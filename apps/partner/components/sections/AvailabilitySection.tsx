"use client";

import { type FormEvent, useCallback, useState } from "react";

import {
  type BlackoutDraft,
  browserTimeZone,
  formatInZone,
  groupRulesByWeekday,
  type RuleDraft,
  shortTime,
  validateBlackoutDraft,
  validateRuleDraft,
  WEEKDAYS,
} from "../../lib/availability";
import type { AvailabilityPreview, AvailabilityRule } from "../../lib/types";
import type { SectionProps } from "../PartnerApp";
import { Alert, Empty, Field, Loading, Panel, useAction, useResource } from "../ui";

const emptyRule = (timezone: string): RuleDraft => ({
  weekday: "0",
  startTime: "08:00",
  endTime: "17:00",
  timezone,
  validFrom: "",
  validUntil: "",
  workerId: "",
});

const emptyBlackout = (timezone: string): BlackoutDraft => ({ startsAt: "", endsAt: "", timezone, reason: "", workerId: "" });

function ruleToDraft(rule: AvailabilityRule): RuleDraft {
  return {
    weekday: String(rule.weekday),
    startTime: shortTime(rule.start_time),
    endTime: shortTime(rule.end_time),
    timezone: rule.timezone,
    validFrom: rule.valid_from ?? "",
    validUntil: rule.valid_until ?? "",
    workerId: rule.worker_id ?? "",
  };
}

export function AvailabilitySection({ api }: SectionProps) {
  const load = useCallback(async () => {
    const [snapshot, workers] = await Promise.all([api.availability(), api.workers()]);
    return { snapshot, workers: workers.items };
  }, [api]);
  const resource = useResource(load);
  const action = useAction();
  const [ruleDraft, setRuleDraft] = useState<RuleDraft | null>(null);
  const [editing, setEditing] = useState<AvailabilityRule | null>(null);
  const [blackoutDraft, setBlackoutDraft] = useState<BlackoutDraft | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [preview, setPreview] = useState<AvailabilityPreview | null>(null);

  if (resource.loading && !resource.data) return <Loading />;
  if (resource.error && !resource.data) return <Alert>{resource.error}</Alert>;
  if (!resource.data) return null;
  const { snapshot, workers } = resource.data;
  const defaultZone = snapshot.rules[0]?.timezone ?? browserTimeZone();
  const rule = ruleDraft ?? emptyRule(defaultZone);
  const blackout = blackoutDraft ?? emptyBlackout(defaultZone);
  const scopeName = (workerId: string | null) => {
    if (!workerId) return "Whole organization";
    const worker = workers.find((item) => item.id === workerId);
    return worker ? `${worker.first_name} ${worker.last_name}` : "Team member";
  };

  async function mutate(task: () => Promise<unknown>, message: string) {
    const ok = await action.run(task, message);
    setPreview(null);
    await resource.reload();
    return ok;
  }

  async function saveRule(event: FormEvent) {
    event.preventDefault();
    const { input, errors: problems } = validateRuleDraft(rule);
    setErrors(problems);
    if (!input) return;
    const ok = editing
      ? await mutate(() => api.updateRule(editing.id, {
          weekday: input.weekday,
          start_time: input.start_time,
          end_time: input.end_time,
          timezone: input.timezone,
          valid_from: input.valid_from,
          valid_until: input.valid_until,
        }, editing.version), "Weekly window updated.")
      : await mutate(() => api.addRule(input), "Weekly window added.");
    if (ok) {
      setEditing(null);
      setRuleDraft(null);
    }
  }

  async function saveBlackout(event: FormEvent) {
    event.preventDefault();
    const { input, errors: problems } = validateBlackoutDraft(blackout);
    setErrors(problems);
    if (!input) return;
    if (await mutate(() => api.addBlackout(input), "Blackout added.")) setBlackoutDraft(null);
  }

  async function loadPreview() {
    const start = new Date();
    const end = new Date(start.getTime() + 7 * 24 * 3600 * 1000);
    await action.run(async () => setPreview(await api.availabilityPreview(start.toISOString(), end.toISOString())));
  }

  const grouped = groupRulesByWeekday(snapshot.rules);

  return (
    <>
      <Alert>{errors.join(" ")}</Alert>
      <Alert>{action.error}</Alert>
      <Alert tone="success">{action.notice}</Alert>
      {!snapshot.consumed_by_scheduling && (
        <Alert tone="info">Availability is recorded for review and planning. It does not yet drive automatic booking, dispatch, or assignment.</Alert>
      )}

      <Panel title="Weekly hours" description="Local wall-clock hours in the chosen timezone; daylight-saving changes are handled for you.">
        {snapshot.rules.length === 0 ? (
          <Empty>No weekly hours yet.</Empty>
        ) : (
          <ul className="partner-week">
            {grouped.map((rules, weekday) => (
              <li key={WEEKDAYS[weekday]}>
                <strong>{WEEKDAYS[weekday]}</strong>
                {rules.length === 0 ? <span className="partner-muted">Unavailable</span> : (
                  <ul>
                    {rules.map((item) => (
                      <li key={item.id}>
                        {shortTime(item.start_time)}–{shortTime(item.end_time)} {item.timezone} · {scopeName(item.worker_id)}
                        {(item.valid_from || item.valid_until) && ` · ${item.valid_from ?? "…"} to ${item.valid_until ?? "…"}`}
                        <span className="partner-row-actions">
                          <button type="button" className="partner-link" disabled={action.busy} onClick={() => { setEditing(item); setRuleDraft(ruleToDraft(item)); }}>Edit</button>
                          <button type="button" className="partner-link" disabled={action.busy} onClick={() => void mutate(() => api.deleteRule(item.id, item.version), "Weekly window removed.")}>Remove</button>
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel title={editing ? "Edit weekly window" : "Add weekly window"}>
        <form className="partner-form" onSubmit={(event) => void saveRule(event)}>
          <div className="partner-grid">
            <Field label="Day">
              <select value={rule.weekday} onChange={(e) => setRuleDraft({ ...rule, weekday: e.target.value })}>
                {WEEKDAYS.map((day, index) => <option key={day} value={index}>{day}</option>)}
              </select>
            </Field>
            <Field label="Start"><input type="time" required value={rule.startTime} onChange={(e) => setRuleDraft({ ...rule, startTime: e.target.value })} /></Field>
            <Field label="End"><input type="time" required value={rule.endTime} onChange={(e) => setRuleDraft({ ...rule, endTime: e.target.value })} /></Field>
            <Field label="Timezone" hint="IANA name, e.g. America/Chicago"><input required value={rule.timezone} onChange={(e) => setRuleDraft({ ...rule, timezone: e.target.value })} /></Field>
            <Field label="Effective from (optional)"><input type="date" value={rule.validFrom} onChange={(e) => setRuleDraft({ ...rule, validFrom: e.target.value })} /></Field>
            <Field label="Effective until (optional)"><input type="date" value={rule.validUntil} onChange={(e) => setRuleDraft({ ...rule, validUntil: e.target.value })} /></Field>
            <Field label="Applies to">
              <select value={rule.workerId} disabled={Boolean(editing)} onChange={(e) => setRuleDraft({ ...rule, workerId: e.target.value })}>
                <option value="">Whole organization</option>
                {workers.map((item) => <option key={item.id} value={item.id}>{item.first_name} {item.last_name}</option>)}
              </select>
            </Field>
          </div>
          <div className="partner-actions">
            <button type="submit" className="partner-button" disabled={action.busy}>{editing ? "Save changes" : "Add window"}</button>
            {editing && <button type="button" className="partner-button partner-button--ghost" onClick={() => { setEditing(null); setRuleDraft(null); }}>Cancel</button>}
          </div>
        </form>
      </Panel>

      <Panel title="Blackout periods" description="Time off, holidays, or closures. Entered in local time and stored in UTC.">
        {snapshot.blackouts.length === 0 ? <Empty>No blackout periods.</Empty> : (
          <ul className="partner-list">
            {snapshot.blackouts.map((item) => (
              <li key={item.id}>
                {formatInZone(item.starts_at, item.timezone)} → {formatInZone(item.ends_at, item.timezone)} ({item.timezone}) · {scopeName(item.worker_id)}
                {item.reason && ` · ${item.reason}`}
                <button type="button" className="partner-link" disabled={action.busy} onClick={() => void mutate(() => api.deleteBlackout(item.id, item.version), "Blackout removed.")}>Remove</button>
              </li>
            ))}
          </ul>
        )}
        <form className="partner-form" onSubmit={(event) => void saveBlackout(event)}>
          <div className="partner-grid">
            <Field label="Starts"><input type="datetime-local" required value={blackout.startsAt} onChange={(e) => setBlackoutDraft({ ...blackout, startsAt: e.target.value })} /></Field>
            <Field label="Ends"><input type="datetime-local" required value={blackout.endsAt} onChange={(e) => setBlackoutDraft({ ...blackout, endsAt: e.target.value })} /></Field>
            <Field label="Timezone"><input required value={blackout.timezone} onChange={(e) => setBlackoutDraft({ ...blackout, timezone: e.target.value })} /></Field>
            <Field label="Applies to">
              <select value={blackout.workerId} onChange={(e) => setBlackoutDraft({ ...blackout, workerId: e.target.value })}>
                <option value="">Whole organization</option>
                {workers.map((item) => <option key={item.id} value={item.id}>{item.first_name} {item.last_name}</option>)}
              </select>
            </Field>
            <Field label="Reason (optional)"><input maxLength={500} value={blackout.reason} onChange={(e) => setBlackoutDraft({ ...blackout, reason: e.target.value })} /></Field>
          </div>
          <div className="partner-actions"><button type="submit" className="partner-button" disabled={action.busy}>Add blackout</button></div>
        </form>
      </Panel>

      <Panel title="Next 7 days" actions={<button type="button" className="partner-button partner-button--ghost" disabled={action.busy} onClick={() => void loadPreview()}>Preview</button>}>
        {!preview ? <p className="partner-muted">Preview the concrete hours your weekly windows produce after blackouts.</p> : preview.intervals.length === 0 ? (
          <Empty>No available hours in the next 7 days.</Empty>
        ) : (
          <ul className="partner-list">
            {preview.intervals.map((item) => (
              <li key={`${item.worker_id ?? "org"}-${item.starts_at}`}>
                {formatInZone(item.starts_at, item.timezone)} → {formatInZone(item.ends_at, item.timezone)} · {scopeName(item.worker_id)}
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </>
  );
}
