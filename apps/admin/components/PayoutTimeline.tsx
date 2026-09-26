import { formatDateTime, humanize, shortId } from "../lib/format";
import type { PayoutHistoryEntry } from "../lib/types";

const LABELS: Record<PayoutHistoryEntry["state"], string> = {
  CREATED: "Created for review",
  APPROVED: "Approved",
  SUBMITTED: "Submitted to payout provider",
  SUBMISSION_BLOCKED: "Submission blocked",
  CURRENT: "Current state",
};

export function PayoutTimeline({ history }: { history: PayoutHistoryEntry[] }) {
  return (
    <ol className="admin-timeline">
      {history.map((entry, index) => (
        <li key={`${entry.state}-${index}`}>
          <strong>{LABELS[entry.state]}</strong>
          {entry.state === "CURRENT" && entry.status ? `: ${humanize(entry.status)}` : ""}
          <br />
          <small>
            {entry.occurred_at ? formatDateTime(entry.occurred_at) : "Time not recorded"}
            {entry.actor_id ? ` · by ${shortId(entry.actor_id)}` : ""}
            {entry.detail ? ` · ${entry.detail}` : ""}
          </small>
        </li>
      ))}
    </ol>
  );
}
