"use client";

import { useCallback, useEffect, useState } from "react";

import { formatDateTime } from "../../lib/format";
import {
  applicationStatusView,
  buildOnboardingPatch,
  completionPercent,
  FIELD_LABELS,
  formFromApplication,
  ONBOARDING_STEPS,
  type OnboardingStep,
  stepComplete,
  type WizardForm,
} from "../../lib/onboarding";
import type { OnboardingChecklist, ProviderApplication } from "../../lib/types";
import type { SectionKey, SectionProps } from "../PartnerApp";
import { Alert, Field, Loading, Panel, StatusBadge, useAction, useResource } from "../ui";

const EXTERNAL_TARGET: Record<Exclude<OnboardingStep["managedIn"], "wizard">, { section: SectionKey; action: string }> = {
  services: { section: "services", action: "Choose services" },
  skills: { section: "skills", action: "Add skills" },
  availability: { section: "availability", action: "Set availability" },
  qualifications: { section: "qualifications", action: "Add and submit qualifications" },
};

function WizardFields({
  step,
  form,
  disabled,
  onChange,
}: {
  step: OnboardingStep;
  form: WizardForm;
  disabled: boolean;
  onChange: (next: WizardForm) => void;
}) {
  const bind = (key: keyof WizardForm) => ({
    value: form[key],
    disabled,
    onChange: (event: { target: { value: string } }) => onChange({ ...form, [key]: event.target.value }),
  });
  switch (step.key) {
    case "identity":
      return <Field label="Owner full name"><input autoComplete="name" required {...bind("fullName")} /></Field>;
    case "business":
      return (
        <div className="partner-grid">
          <Field label="Legal business name"><input required {...bind("legalName")} /></Field>
          <Field label="Public display name"><input required {...bind("displayName")} /></Field>
          <Field label="Entity type" hint="For example LLC, corporation, sole proprietor.">
            <input {...bind("entityType")} />
          </Field>
          <Field label="Tax ID — last 4 digits" hint="Never enter the full number.">
            <input inputMode="numeric" maxLength={4} {...bind("taxIdLast4")} />
          </Field>
          <Field label="Years in business"><input inputMode="numeric" {...bind("yearsInBusiness")} /></Field>
        </div>
      );
    case "contact":
      return (
        <div className="partner-grid">
          <Field label="Business email"><input type="email" autoComplete="email" required {...bind("contactEmail")} /></Field>
          <Field label="Business phone"><input type="tel" autoComplete="tel" required {...bind("contactPhone")} /></Field>
        </div>
      );
    case "coverage":
      return (
        <Field label="ZIP codes you serve" hint="Separate with commas or spaces. ZIP or ZIP+4.">
          <textarea rows={4} {...bind("postalCodes")} />
        </Field>
      );
    case "capacity":
      return (
        <div className="partner-grid">
          <Field label="Jobs per day"><input inputMode="numeric" {...bind("dailyJobs")} /></Field>
          <Field label="Crew size"><input inputMode="numeric" {...bind("crewSize")} /></Field>
        </div>
      );
    default:
      return null;
  }
}

export function OnboardingView({
  application,
  checklist,
  form,
  activeStep,
  busy,
  onSelectStep,
  onFormChange,
  onSave,
  onSubmit,
  navigate,
}: {
  application: ProviderApplication;
  checklist: OnboardingChecklist;
  form: WizardForm;
  activeStep: string;
  busy: boolean;
  onSelectStep: (key: string) => void;
  onFormChange: (next: WizardForm) => void;
  onSave: () => void;
  onSubmit: () => void;
  navigate: (key: SectionKey) => void;
}) {
  const status = applicationStatusView(checklist.status);
  const step = ONBOARDING_STEPS.find((item) => item.key === activeStep) ?? ONBOARDING_STEPS[0];
  const locked = !checklist.editable;
  const percent = completionPercent(checklist);
  const external = step.managedIn === "wizard" ? null : EXTERNAL_TARGET[step.managedIn];

  return (
    <>
      <Panel
        title="Application status"
        description={status.message}
        actions={<StatusBadge label={status.label} tone={status.tone} />}
      >
        {checklist.requested_information && (
          <Alert tone="warning">BREERO requested: {checklist.requested_information}</Alert>
        )}
        {checklist.decision_reason && (
          <Alert tone={checklist.status === "APPROVED" ? "success" : "danger"}>Decision note: {checklist.decision_reason}</Alert>
        )}
        <dl className="partner-meta">
          <div><dt>Submitted</dt><dd>{formatDateTime(checklist.submitted_at)}</dd></div>
          <div><dt>Decided</dt><dd>{formatDateTime(checklist.decided_at)}</dd></div>
          <div><dt>Progress</dt><dd>{percent}% complete</dd></div>
        </dl>
        <div className="partner-progress" role="progressbar" aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100}>
          <span style={{ width: `${percent}%` }} />
        </div>
      </Panel>

      <div className="partner-wizard">
        <ol className="partner-steps" aria-label="Onboarding steps">
          {ONBOARDING_STEPS.map((item) => {
            const complete = stepComplete(item, checklist);
            return (
              <li key={item.key}>
                <button
                  type="button"
                  className={item.key === step.key ? "is-active" : ""}
                  aria-current={item.key === step.key ? "step" : undefined}
                  onClick={() => onSelectStep(item.key)}
                >
                  <span aria-hidden="true">{complete ? "✓" : "•"}</span> {item.label}
                  <span className="partner-sr">{complete ? " (complete)" : " (incomplete)"}</span>
                </button>
              </li>
            );
          })}
        </ol>

        <Panel title={step.label}>
          {step.managedIn === "wizard" ? (
            <form
              className="partner-form"
              onSubmit={(event) => {
                event.preventDefault();
                onSave();
              }}
            >
              <WizardFields step={step} form={form} disabled={locked || busy} onChange={onFormChange} />
              {!locked && (
                <div className="partner-actions">
                  <button type="submit" className="partner-button" disabled={busy}>Save progress</button>
                </div>
              )}
            </form>
          ) : (
            <div>
              <p>
                {stepComplete(step, checklist)
                  ? "This step is complete."
                  : `Still needed: ${step.fields.filter((field) => checklist.missing.includes(field)).map((field) => FIELD_LABELS[field] ?? field).join(", ")}.`}
              </p>
              {external && (
                <button type="button" className="partner-button partner-button--ghost" onClick={() => navigate(external.section)}>
                  {external.action}
                </button>
              )}
            </div>
          )}
        </Panel>
      </div>

      {checklist.editable && (
        <Panel title="Submit for review" description="Submitting locks your application and service selections until BREERO decides.">
          {checklist.missing.length > 0 && (
            <p className="partner-muted">Outstanding: {checklist.missing.map((field) => FIELD_LABELS[field] ?? field).join(", ")}.</p>
          )}
          <button type="button" className="partner-button" disabled={busy || !checklist.submittable} onClick={onSubmit}>
            {application.status === "INFORMATION_REQUESTED" ? "Resubmit application" : "Submit application"}
          </button>
        </Panel>
      )}
    </>
  );
}

export function OnboardingSection({ api, navigate }: SectionProps) {
  const load = useCallback(async () => {
    const [application, checklist] = await Promise.all([api.onboarding(), api.onboardingChecklist()]);
    return { application, checklist };
  }, [api]);
  const resource = useResource(load);
  const action = useAction();
  const [form, setForm] = useState<WizardForm | null>(null);
  const [activeStep, setActiveStep] = useState(ONBOARDING_STEPS[0].key);
  const [formErrors, setFormErrors] = useState<string[]>([]);

  useEffect(() => {
    if (resource.data) setForm(formFromApplication(resource.data.application));
  }, [resource.data]);

  if (resource.loading && !resource.data) return <Loading />;
  if (resource.error && !resource.data) return <Alert>{resource.error}</Alert>;
  if (!resource.data || !form) return null;
  const { application, checklist } = resource.data;

  async function save() {
    if (!form) return;
    const { patch, errors } = buildOnboardingPatch(form, application);
    setFormErrors(errors);
    if (errors.length) return;
    await action.run(() => api.saveOnboarding(patch, application.version), "Progress saved.");
    await resource.reload();
  }

  async function submit() {
    await action.run(() => api.submitOnboarding(application.version), "Application submitted for review.");
    await resource.reload();
  }

  return (
    <>
      <Alert>{formErrors.join(" ")}</Alert>
      <Alert>{action.error}</Alert>
      <Alert tone="success">{action.notice}</Alert>
      <OnboardingView
        application={application}
        checklist={checklist}
        form={form}
        activeStep={activeStep}
        busy={action.busy}
        onSelectStep={setActiveStep}
        onFormChange={setForm}
        onSave={() => void save()}
        onSubmit={() => void submit()}
        navigate={navigate}
      />
    </>
  );
}
