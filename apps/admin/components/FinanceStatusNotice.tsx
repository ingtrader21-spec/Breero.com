import { humanize } from "../lib/format";
import type { FinanceStatus } from "../lib/types";
import { Notice } from "./ui";

/** Makes disabled and not-implemented finance capabilities explicit instead of hiding them. */
export function FinanceStatusNotice({ status }: { status: FinanceStatus }) {
  const notImplemented = Object.entries(status.capabilities).filter(([, state]) => state === "NOT_IMPLEMENTED").map(([name]) => humanize(name));
  return (
    <>
      {!status.payouts_enabled && (
        <Notice tone="warning" title="Payout commands disabled">
          PAYOUT_ENABLED is off for this environment. Batches, earnings and history remain readable; creating, approving and submitting batches is unavailable.
        </Notice>
      )}
      {notImplemented.length > 0 && (
        <Notice title="Not implemented">
          {notImplemented.join(", ")}: these capabilities are not exposed by any finance API and fail closed. No placeholder controls are shown.
        </Notice>
      )}
    </>
  );
}
