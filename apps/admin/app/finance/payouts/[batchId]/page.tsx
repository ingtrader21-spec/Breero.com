"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback } from "react";
import { PageHeader, useAdmin } from "../../../../components/AdminShell";
import { ConfirmAction } from "../../../../components/ConfirmAction";
import { FinanceStatusNotice } from "../../../../components/FinanceStatusNotice";
import { PayoutTimeline } from "../../../../components/PayoutTimeline";
import { ErrorMessage, KeyValues, Loading, Notice, Section, StatusBadge } from "../../../../components/ui";
import { formatDateTime, formatMinor, humanize, shortId } from "../../../../lib/format";
import { ACTION_COPY, payoutViewState } from "../../../../lib/payouts";
import { useResource } from "../../../../lib/useResource";

export default function PayoutBatchPage() {
  const params = useParams<{ batchId: string }>();
  const batchId = params?.batchId ?? "";
  const { api } = useAdmin();
  const finance = useResource(useCallback(() => api.financeStatus(), [api]));
  const loadBatch = useCallback(() => api.getPayoutBatch(batchId), [api, batchId]);
  const batch = useResource(batchId ? loadBatch : null);
  const data = batch.data;
  const view = data ? payoutViewState(data, finance.data) : null;

  return (
    <>
      <PageHeader eyebrow="Payout batches" title={data?.reference ?? "Payout batch"}>
        <p><Link href="/finance/payouts">← All batches</Link></p>
      </PageHeader>
      {finance.data && <FinanceStatusNotice status={finance.data} />}
      <Loading active={batch.loading && !data} />
      <ErrorMessage error={batch.error} />
      {data && view && (
        <>
          <Section title={view.headline} actions={<StatusBadge value={data.status} tone={view.tone} />}>
            <KeyValues rows={[
              { label: "Total", value: formatMinor(data.total_minor, data.currency) },
              { label: "Earnings", value: String(data.earning_count) },
              { label: "Reviewed by", value: shortId(data.reviewed_by) },
              { label: "Approved by", value: shortId(data.approved_by) },
              { label: "Submitted", value: formatDateTime(data.submitted_at) },
              { label: "Provider status", value: data.provider_status ?? "—" },
              { label: "Provider reference", value: data.provider_reference ?? "—" },
            ]} />
            {data.failure_reason && <Notice tone="danger" title="Failure reason">{data.failure_reason}</Notice>}
            {view.blockedReason && <Notice tone="warning">{view.blockedReason}</Notice>}
            <div className="admin-actions">
              {view.actions.map((action) => (
                <ConfirmAction
                  key={action}
                  label={ACTION_COPY[action].label}
                  title={`${ACTION_COPY[action].label}: ${data.reference}`}
                  description={`${ACTION_COPY[action].confirm} Total ${formatMinor(data.total_minor, data.currency)} across ${data.earning_count} earning(s).`}
                  confirmLabel={ACTION_COPY[action].label}
                  onConfirm={async () => {
                    try {
                      if (action === "approve") await api.approvePayoutBatch(data.id);
                      else await api.submitPayoutBatch(data.id);
                    } finally {
                      // Always read back persisted state, including fail-closed submission errors.
                      batch.reload();
                    }
                  }}
                />
              ))}
            </div>
          </Section>
          <Section title="History">
            <PayoutTimeline history={data.history} />
          </Section>
          <Section title="Vendor totals">
            <div className="portal-table-wrap">
              <table>
                <thead><tr><th>Vendor</th><th>Earnings</th><th>Total</th></tr></thead>
                <tbody>
                  {data.vendor_totals.map((row) => (
                    <tr key={row.vendor_id}><td>{row.vendor_id}</td><td>{row.earning_count}</td><td>{formatMinor(row.total_minor, data.currency)}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
          <Section title="Earnings in batch">
            <div className="portal-table-wrap">
              <table>
                <thead><tr><th>Earning</th><th>Vendor</th><th>Job</th><th>Net</th><th>Adjustments</th><th>Payable</th><th>Status</th></tr></thead>
                <tbody>
                  {data.earnings.map((earning) => (
                    <tr key={earning.id}>
                      <td>{shortId(earning.id)}</td>
                      <td>{shortId(earning.vendor_id)}</td>
                      <td>{shortId(earning.job_id)}</td>
                      <td>{formatMinor(earning.net_minor, earning.currency)}</td>
                      <td>{formatMinor(earning.adjustment_total_minor, earning.currency)}</td>
                      <td>{formatMinor(earning.payable_minor, earning.currency)}</td>
                      <td>{humanize(earning.status)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
        </>
      )}
    </>
  );
}
