import type { ApplicationStatus, OnboardingChecklist, OnboardingPatch, ProviderApplication } from "./types";

export type Tone = "neutral" | "info" | "success" | "warning" | "danger";

export interface StatusView { label: string; tone: Tone; message: string }

export function applicationStatusView(status: ApplicationStatus): StatusView {
  switch (status) {
    case "DRAFT":
      return { label: "Draft", tone: "neutral", message: "Complete each step, save your progress, and submit when every requirement is met." };
    case "PENDING":
      return { label: "Under review", tone: "info", message: "BREERO is reviewing your application. Details are locked until a decision is made." };
    case "INFORMATION_REQUESTED":
      return { label: "Information requested", tone: "warning", message: "BREERO needs more information. Update the requested details and resubmit." };
    case "APPROVED":
      return { label: "Approved", tone: "success", message: "Your provider account is approved. Offers can reach your team once operations activates dispatch." };
    case "REJECTED":
      return { label: "Not approved", tone: "danger", message: "This application was not approved. Contact BREERO provider support for next steps." };
  }
}

export interface OnboardingStep {
  key: string;
  label: string;
  /** Application fields this step satisfies. */
  fields: string[];
  /** Where the data is managed. `wizard` steps are edited inline. */
  managedIn: "wizard" | "services" | "skills" | "availability" | "qualifications";
}

export const ONBOARDING_STEPS: OnboardingStep[] = [
  { key: "identity", label: "Owner identity", fields: ["identity"], managedIn: "wizard" },
  { key: "business", label: "Business details", fields: ["business"], managedIn: "wizard" },
  { key: "contact", label: "Contact details", fields: ["contact_details"], managedIn: "wizard" },
  { key: "coverage", label: "Service area", fields: ["service_areas", "postal_codes"], managedIn: "wizard" },
  { key: "capacity", label: "Capacity", fields: ["capacity"], managedIn: "wizard" },
  { key: "services", label: "Services offered", fields: ["services"], managedIn: "services" },
  { key: "skills", label: "Professional skills", fields: ["skills"], managedIn: "skills" },
  { key: "availability", label: "Availability", fields: ["availability"], managedIn: "availability" },
  { key: "qualifications", label: "Licenses, insurance & documents", fields: ["licenses", "insurance", "compliance_documents"], managedIn: "qualifications" },
];

export function stepComplete(step: OnboardingStep, checklist: Pick<OnboardingChecklist, "missing">): boolean {
  return step.fields.every((field) => !checklist.missing.includes(field));
}

export function completionPercent(checklist: Pick<OnboardingChecklist, "missing">): number {
  const done = ONBOARDING_STEPS.filter((step) => stepComplete(step, checklist)).length;
  return Math.round((done / ONBOARDING_STEPS.length) * 100);
}

export interface WizardForm {
  fullName: string;
  legalName: string;
  displayName: string;
  entityType: string;
  taxIdLast4: string;
  yearsInBusiness: string;
  contactEmail: string;
  contactPhone: string;
  postalCodes: string;
  dailyJobs: string;
  crewSize: string;
}

const text = (value: unknown): string => (typeof value === "string" || typeof value === "number" ? String(value) : "");

export function formFromApplication(application: ProviderApplication): WizardForm {
  return {
    fullName: text(application.identity.full_name),
    legalName: text(application.business.legal_name),
    displayName: text(application.business.display_name),
    entityType: text(application.business.entity_type),
    taxIdLast4: text(application.business.tax_id_last4),
    yearsInBusiness: text(application.business.years_in_business),
    contactEmail: text(application.contact_details.email),
    contactPhone: text(application.contact_details.phone),
    postalCodes: application.postal_codes.join(", "),
    dailyJobs: text(application.capacity.daily_jobs),
    crewSize: text(application.capacity.crew_size),
  };
}

const ZIP_RE = /^\d{5}(-\d{4})?$/;

export function parsePostalCodes(raw: string): { codes: string[]; invalid: string[] } {
  const tokens = raw.split(/[\s,;]+/).map((item) => item.trim()).filter(Boolean);
  const codes: string[] = [];
  const invalid: string[] = [];
  for (const token of tokens) {
    if (!ZIP_RE.test(token)) invalid.push(token);
    else if (!codes.includes(token)) codes.push(token);
  }
  return { codes, invalid };
}

function positiveInt(value: string): number | undefined {
  if (!/^\d+$/.test(value.trim())) return undefined;
  const parsed = Number.parseInt(value, 10);
  return parsed > 0 ? parsed : undefined;
}

function compact(value: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(value).filter(([, item]) => item !== undefined && item !== ""));
}

export interface PatchResult { patch: OnboardingPatch; errors: string[] }

/**
 * Builds the onboarding PATCH body. Only wizard-owned fields are sent: services and
 * skills are rejected by the API here, and availability/credentials come from their
 * dedicated provider records.
 */
export function buildOnboardingPatch(form: WizardForm, previous: ProviderApplication): PatchResult {
  const errors: string[] = [];
  const { codes, invalid } = parsePostalCodes(form.postalCodes);
  if (invalid.length) errors.push(`Invalid ZIP codes: ${invalid.join(", ")}`);
  if (form.taxIdLast4 && !/^\d{4}$/.test(form.taxIdLast4)) errors.push("Tax ID must be the last four digits only.");
  const dailyJobs = form.dailyJobs ? positiveInt(form.dailyJobs) : undefined;
  if (form.dailyJobs && dailyJobs === undefined) errors.push("Daily job capacity must be a positive whole number.");
  const crewSize = form.crewSize ? positiveInt(form.crewSize) : undefined;
  if (form.crewSize && crewSize === undefined) errors.push("Crew size must be a positive whole number.");
  const years = form.yearsInBusiness ? Number.parseInt(form.yearsInBusiness, 10) : undefined;
  if (form.yearsInBusiness && (years === undefined || Number.isNaN(years) || years < 0 || years > 200)) {
    errors.push("Years in business must be between 0 and 200.");
  }

  const patch: OnboardingPatch = {
    identity: compact({ ...previous.identity, full_name: form.fullName.trim() }),
    business: compact({
      ...previous.business,
      legal_name: form.legalName.trim(),
      display_name: form.displayName.trim(),
      entity_type: form.entityType.trim(),
      tax_id_last4: form.taxIdLast4.trim(),
      years_in_business: years,
    }),
    contact_details: compact({ ...previous.contact_details, email: form.contactEmail.trim().toLowerCase(), phone: form.contactPhone.trim() }),
    postal_codes: codes,
    service_areas: codes.map((code) => ({ type: "ZIP", value: code })),
    capacity: compact({ ...previous.capacity, daily_jobs: dailyJobs, crew_size: crewSize }),
  };
  return { patch, errors };
}

export const FIELD_LABELS: Record<string, string> = {
  identity: "Owner identity",
  business: "Business details",
  contact_details: "Contact details",
  services: "Services offered",
  skills: "Professional skills",
  service_areas: "Service area",
  postal_codes: "ZIP codes",
  availability: "Availability",
  capacity: "Capacity",
  licenses: "Submitted license",
  insurance: "Submitted insurance",
  compliance_documents: "Submitted compliance documents",
};
