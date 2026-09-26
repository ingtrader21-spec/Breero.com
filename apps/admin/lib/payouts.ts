import type { FinanceStatus, PayoutAction, PayoutBatchDetail, PayoutStatus } from "./types";

export type Tone = "neutral" | "info" | "success" | "warning" | "danger";

export const PAYOUT_STATUS_TONE: Record<PayoutStatus, Tone> = {
  DRAFT: "neutral",
  PENDING_APPROVAL: "warning",
  APPROVED: "info",
  PROCESSING: "info",
  PAID: "success",
  FAILED: "danger",
  CANCELLED: "neutral",
};

export interface PayoutViewState {
  headline: string;
  tone: Tone;
  actions: PayoutAction[];
  /** Why no action is available, when that is the case. */
  blockedReason: string | null;
}

/**
 * Derives the payout screen state purely from the server read model. The server
 * decides allowed actions (including four-eyes and the PAYOUT_ENABLED gate); the
 * UI never widens them.
 */
export function payoutViewState(batch: PayoutBatchDetail, status?: FinanceStatus | null): PayoutViewState {
  const tone = PAYOUT_STATUS_TONE[batch.status];
  const payoutsEnabled = batch.payouts_enabled && (status?.payouts_enabled ?? true);
  const actions = payoutsEnabled ? batch.allowed_actions : [];
  let headline: string;
  switch (batch.status) {
    case "PENDING_APPROVAL": headline = "Awaiting second-person approval"; break;
    case "APPROVED": headline = batch.failure_reason ? "Approved — submission blocked" : "Approved — ready to submit"; break;
    case "PROCESSING": headline = "Submitted — awaiting provider settlement"; break;
    case "PAID": headline = "Paid"; break;
    case "FAILED": headline = "Payout failed"; break;
    case "CANCELLED": headline = "Cancelled"; break;
    default: headline = "Draft";
  }
  let blockedReason: string | null = null;
  if (!payoutsEnabled) {
    blockedReason = "Payout commands are disabled on this environment (PAYOUT_ENABLED=false). This batch is read-only.";
  } else if (actions.length === 0 && batch.status === "PENDING_APPROVAL") {
    blockedReason = "You reviewed this batch, so a different finance approver must approve it.";
  } else if (actions.length === 0 && batch.status === "APPROVED" && batch.failure_reason) {
    blockedReason = `Submission is blocked: ${batch.failure_reason}.`;
  }
  if (status?.capabilities.payout_transfer === "NOT_IMPLEMENTED" && actions.includes("submit")) {
    blockedReason = "No live payout transfer adapter is configured; submission will fail closed and the batch stays approved.";
  }
  return { headline, tone, actions, blockedReason };
}

export const ACTION_COPY: Record<PayoutAction, { label: string; confirm: string }> = {
  approve: {
    label: "Approve batch",
    confirm: "Approving records your second-person sign-off. Funds are not moved until the batch is submitted.",
  },
  submit: {
    label: "Submit to payout provider",
    confirm: "Submission sends this batch to the configured payout provider using a stable idempotency key.",
  },
};
