import type { StatusView } from "./onboarding";
import type { Qualification, QualificationInput, QualificationType } from "./types";

export const QUALIFICATION_TYPES: { value: QualificationType; label: string }[] = [
  { value: "LICENSE", label: "License" },
  { value: "INSURANCE", label: "Insurance" },
  { value: "CERTIFICATION", label: "Certification" },
  { value: "BACKGROUND_CHECK", label: "Background check" },
  { value: "TRAINING", label: "Training" },
  { value: "OTHER", label: "Other" },
];

const EXPIRY_REQUIRED: QualificationType[] = ["LICENSE", "INSURANCE"];
const EVIDENCE_RE = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;

export function qualificationStatusView(item: Pick<Qualification, "status" | "review_status" | "is_expired">): StatusView {
  if (item.status === "WITHDRAWN") return { label: "Withdrawn", tone: "neutral", message: "Withdrawn by your organization." };
  if (item.is_expired) return { label: "Expired", tone: "danger", message: "Add a current record and submit it for review." };
  switch (item.review_status) {
    case "NOT_SUBMITTED":
      return { label: "Draft", tone: "neutral", message: "Submit this record so BREERO can review it." };
    case "PENDING_REVIEW":
      return { label: "Pending review", tone: "info", message: "BREERO is reviewing this record. It is locked until a decision is made." };
    case "APPROVED":
      return { label: "Approved", tone: "success", message: "Reviewed and accepted by BREERO." };
    case "REJECTED":
      return { label: "Rejected", tone: "danger", message: "Update the details and resubmit." };
    case "INFORMATION_REQUESTED":
      return { label: "Information requested", tone: "warning", message: "Update the details and resubmit." };
  }
}

export function canEditQualification(item: Pick<Qualification, "status" | "review_status">): boolean {
  if (item.status === "WITHDRAWN") return false;
  return ["NOT_SUBMITTED", "REJECTED", "INFORMATION_REQUESTED"].includes(item.review_status);
}

export function canSubmitQualification(item: Pick<Qualification, "status" | "is_expired">): boolean {
  return item.status === "DRAFT" && !item.is_expired;
}

export interface QualificationDraft {
  qualificationType: QualificationType;
  title: string;
  issuer: string;
  jurisdiction: string;
  referenceLast4: string;
  issuedOn: string;
  expiresOn: string;
  evidenceReference: string;
  workerId: string;
}

export const emptyQualificationDraft = (): QualificationDraft => ({
  qualificationType: "LICENSE",
  title: "",
  issuer: "",
  jurisdiction: "",
  referenceLast4: "",
  issuedOn: "",
  expiresOn: "",
  evidenceReference: "",
  workerId: "",
});

export function validateQualificationDraft(draft: QualificationDraft, today: string): { input?: QualificationInput; errors: string[] } {
  const errors: string[] = [];
  const title = draft.title.trim();
  const jurisdiction = draft.jurisdiction.trim().toUpperCase();
  const reference = draft.referenceLast4.trim();
  const evidence = draft.evidenceReference.trim();
  if (!title) errors.push("Title is required.");
  if (title.length > 160) errors.push("Title must be 160 characters or fewer.");
  if (jurisdiction && !/^[A-Z]{2,3}$/.test(jurisdiction)) errors.push("Jurisdiction must be a 2–3 letter code such as TX or US.");
  if (reference && !/^[A-Za-z0-9]{4}$/.test(reference)) errors.push("Enter only the last four characters of the reference number.");
  if (evidence && !EVIDENCE_RE.test(evidence)) errors.push("Evidence reference must be an ID (letters, digits, . _ : -), not a link.");
  if (draft.issuedOn && draft.expiresOn && draft.issuedOn > draft.expiresOn) errors.push("Issue date must not be after expiry.");
  if (EXPIRY_REQUIRED.includes(draft.qualificationType) && !draft.expiresOn) errors.push("Licenses and insurance need an expiry date.");
  if (draft.expiresOn && draft.expiresOn < today) errors.push("This record has already expired.");
  if (errors.length) return { errors };
  return {
    errors,
    input: {
      qualification_type: draft.qualificationType,
      title,
      issuer: draft.issuer.trim() || null,
      jurisdiction: jurisdiction || null,
      reference_last4: reference || null,
      issued_on: draft.issuedOn || null,
      expires_on: draft.expiresOn || null,
      evidence_reference: evidence || null,
      ...(draft.workerId ? { worker_id: draft.workerId } : {}),
    },
  };
}
