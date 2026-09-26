import type { ProviderApplication, ProviderApplicationStatus } from "./types";
import type { Tone } from "./payouts";

export type ProviderDecision = "approve" | "reject" | "request-information";

export const APPLICATION_STATUS_TONE: Record<ProviderApplicationStatus, Tone> = {
  DRAFT: "neutral",
  PENDING: "warning",
  INFORMATION_REQUESTED: "info",
  APPROVED: "success",
  REJECTED: "danger",
};

export const DECISION_COPY: Record<ProviderDecision, { label: string; confirm: string; reasonLabel: string }> = {
  approve: {
    label: "Approve",
    confirm: "Approving activates the provider organization and its workers, and approves its pending services and skills.",
    reasonLabel: "Approval note",
  },
  reject: {
    label: "Reject",
    confirm: "Rejecting closes this application and records the reason you give.",
    reasonLabel: "Rejection reason",
  },
  "request-information": {
    label: "Request information",
    confirm: "The application returns to the provider with your request. They can resubmit afterwards.",
    reasonLabel: "Information requested",
  },
};

/** Decisions are only accepted by the API while an application is PENDING review. */
export function allowedDecisions(application: Pick<ProviderApplication, "status">): ProviderDecision[] {
  return application.status === "PENDING" ? ["approve", "request-information", "reject"] : [];
}

export function validateDecisionReason(reason: string): string | null {
  const trimmed = reason.trim();
  if (trimmed.length < 3) return "Enter at least 3 characters.";
  if (trimmed.length > 1000) return "Keep the reason under 1000 characters.";
  return null;
}

/** Flattens a JSON section of the application into label/value rows for review. */
export function sectionRows(section: unknown): { label: string; value: string }[] {
  if (!section || typeof section !== "object") return [];
  if (Array.isArray(section)) {
    return section.map((item, index) => ({ label: `#${index + 1}`, value: typeof item === "object" ? JSON.stringify(item) : String(item) }));
  }
  return Object.entries(section as Record<string, unknown>).map(([key, value]) => ({
    label: key.replaceAll("_", " "),
    value: value === null || value === undefined ? "—" : typeof value === "object" ? JSON.stringify(value) : String(value),
  }));
}
