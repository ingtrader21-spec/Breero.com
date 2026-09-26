"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";
import { PageHeader, useAdmin } from "../../../components/AdminShell";
import { ConfirmAction } from "../../../components/ConfirmAction";
import { FinanceStatusNotice } from "../../../components/FinanceStatusNotice";
import { Empty, ErrorMessage, KeyValues, Loading, Pager, Section, StatusBadge } from "../../../components/ui";
import { formatDateTime, formatMinor, humanize } from "../../../lib/format";
import { PAYOUT_STATUS_TONE } from "../../../lib/payouts";
import type { PayoutStatus } from "../../../lib/types";
import { useResource } from "../../../lib/useResource";

const STATUSES: PayoutStatus[] = ["PENDING_APPROVAL", "APPROVED", "PROCESSING", "PAID", "FAILED", "CANCELLED"];
const PAGE_SIZE = 25;

export default function PayoutBatchesPage() {
  const { api } = useAdmin();
  const [status, setStatus] = useState<"" | PayoutStatus>("");
  const [page, setPage] = useState(1);
  const finance = useResource(useCallback(() => api.financeStatus(), [api]));
  const batches = useResource(useCallback(
    () => api.listPayoutBatches({ status: status || undefined, page, page_size: PAGE_SIZE }),
    [api, status, page],
  ));

  return (
    <>
      <PageHeader eyebrow="Finance" title="Payout batches" />
      <ErrorMessage error={finance.error} />
      {finance.data && <FinanceStatusNotice status={finance.data} />}
      {finance.data?.payouts_enabled && <CreateBatch />}
      <Section
        title="Batches"
        actions={(
          <label className="admin-form">Status
            <select value={status} onChange={(event) => { setPage(1); setStatus(event.target.value as typeof status); }}>
              <option value="">All</option>
              {STATUSES.map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
            </select>
          </label>
        )}
      >
        <Loading active={batches.loading} />
        <ErrorMessage error={batches.error} />
        {batches.data && batches.data.items.length === 0 && <Empty>No payout batches.</Empty>}
        {batches.data && batches.data.items.length > 0 && (
          <>
            <div className="portal-table-wrap">
              <table>
                <thead><tr><th>Reference</th><th>Status</th><th>Total</th><th>Earnings</th><th>Created</th><th>Submitted</th></tr></thead>
                <tbody>
                  {batches.data.items.map((batch) => (
                    <tr key={batch.id}>
                      <td><Link href={`/finance/payouts/${batch.id}`}>{batch.reference}</Link></td>
                      <td><StatusBadge value={batch.status} tone={PAYOUT_STATUS_TONE[batch.status]} /></td>
                      <td>{formatMinor(batch.total_minor, batch.currency)}</td>
                      <td>{batch.earning_count}</td>
                      <td>{formatDateTime(batch.created_at)}</td>
                      <td>{formatDateTime(batch.submitted_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager page={batches.data.page} pageSize={batches.data.page_size} total={batches.data.total} onPage={setPage} />
          </>
        )}
      </Section>
    </>
  );
}

function CreateBatch() {
  const { api } = useAdmin();
  const router = useRouter();
  const [currency, setCurrency] = useState("USD");
  const [vendorId, setVendorId] = useState("");
  const validCurrency = /^[A-Z]{3}$/.test(currency);
  const validVendor = !vendorId.trim() || /^[0-9a-f-]{36}$/i.test(vendorId.trim());
  const canLoad = validCurrency && validVendor;
  const loadCandidates = useCallback(
    () => api.payoutCandidates(currency, vendorId.trim() || undefined),
    [api, currency, vendorId],
  );
  const candidates = useResource(canLoad ? loadCandidates : null);

  return (
    <Section title="Review eligible earnings">
      <p>Batches collect AVAILABLE earnings whose hold period has ended. The batch is created for review; a different finance user must approve it.</p>
      <div className="admin-form admin-form--inline">
        <label>Currency<input value={currency} maxLength={3} onChange={(event) => setCurrency(event.target.value.toUpperCase())} /></label>
        <label>Vendor ID (optional)<input value={vendorId} onChange={(event) => setVendorId(event.target.value)} /></label>
      </div>
      {!canLoad && <p className="portal-error" role="alert">Enter a 3-letter currency and, optionally, a full vendor UUID.</p>}
      {canLoad && <ErrorMessage error={candidates.error} />}
      {canLoad && candidates.data && (
        <>
          <KeyValues rows={[
            { label: "Eligible earnings", value: String(candidates.data.earning_count) },
            { label: "Eligible total", value: formatMinor(candidates.data.total_minor, candidates.data.currency) },
          ]} />
          <ConfirmAction
            label="Create batch for review"
            title="Create a payout batch?"
            description={`${candidates.data.earning_count} earning(s) totalling ${formatMinor(candidates.data.total_minor, candidates.data.currency)} will be locked into a batch awaiting approval. No money moves at this step.`}
            confirmLabel="Create batch"
            disabled={candidates.data.earning_count === 0}
            onConfirm={async () => {
              const batch = await api.createPayoutBatch(currency, vendorId.trim() || undefined);
              router.push(`/finance/payouts/${batch.id}`);
            }}
          />
        </>
      )}
    </Section>
  );
}
