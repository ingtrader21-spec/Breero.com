"use client";

import Link from "next/link";
import { useCallback } from "react";
import { PageHeader, useAdmin } from "../../components/AdminShell";
import { FinanceStatusNotice } from "../../components/FinanceStatusNotice";
import { Empty, ErrorMessage, Loading, Section, StatusBadge } from "../../components/ui";
import { formatDateTime, formatMinor, humanize, shortId } from "../../lib/format";
import { useResource } from "../../lib/useResource";

export default function FinanceOverviewPage() {
  const { api } = useAdmin();
  const status = useResource(useCallback(() => api.financeStatus(), [api]));
  const summary = useResource(useCallback(() => api.earningsSummary(), [api]));
  const exceptions = useResource(useCallback(() => api.financeExceptions(), [api]));

  return (
    <>
      <PageHeader eyebrow="Finance" title="Finance overview" />
      <ErrorMessage error={status.error} />
      {status.data && <FinanceStatusNotice status={status.data} />}
      <Section title="Pending payout totals">
        <p>All amounts are read from persisted earnings. The portal never calculates liabilities.</p>
        <Loading active={summary.loading} />
        <ErrorMessage error={summary.error} />
        {summary.data && summary.data.pending_payouts.length === 0 && <Empty>No earnings recorded.</Empty>}
        <div className="admin-grid">
          {summary.data?.pending_payouts.map((total) => (
            <article key={total.currency} className="admin-card">
              <h3>{total.currency}</h3>
              <p>Eligible now ({total.eligible_count})</p>
              <p className="admin-metric">{formatMinor(total.eligible_minor, total.currency)}</p>
              <p>Pending release: {formatMinor(total.pending_release_minor, total.currency)}</p>
              <p>On hold: {formatMinor(total.held_minor, total.currency)}</p>
              <p>In batches: {formatMinor(total.in_batch_minor, total.currency)}</p>
              <p>Paid: {formatMinor(total.paid_minor, total.currency)}</p>
            </article>
          ))}
        </div>
      </Section>
      <Section title="Earnings by status">
        {summary.data && summary.data.by_status.length > 0 && (
          <div className="portal-table-wrap">
            <table>
              <thead><tr><th>Currency</th><th>Status</th><th>Earnings</th><th>Payable</th></tr></thead>
              <tbody>
                {summary.data.by_status.map((row) => (
                  <tr key={`${row.currency}:${row.status}`}>
                    <td>{row.currency}</td><td>{humanize(row.status)}</td><td>{row.earning_count}</td><td>{formatMinor(row.payable_minor, row.currency)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>
      <Section title="Exceptions">
        <Loading active={exceptions.loading} />
        <ErrorMessage error={exceptions.error} />
        {exceptions.data && exceptions.data.items.length === 0 && <Empty>No finance exceptions.</Empty>}
        {exceptions.data && exceptions.data.items.length > 0 && (
          <div className="portal-table-wrap">
            <table>
              <thead><tr><th>Kind</th><th>Record</th><th>Status</th><th>Amount</th><th>Reason</th><th>When</th></tr></thead>
              <tbody>
                {exceptions.data.items.map((item) => (
                  <tr key={`${item.kind}:${item.resource_id}`}>
                    <td><StatusBadge value={item.kind} tone={item.kind === "PAYOUT_FAILED" || item.kind === "EARNING_REVERSED" ? "danger" : "warning"} /></td>
                    <td>
                      {item.resource_type === "payout_batch"
                        ? <Link href={`/finance/payouts/${item.resource_id}`}>{item.reference ?? shortId(item.resource_id)}</Link>
                        : `Earning ${shortId(item.resource_id)} · vendor ${shortId(item.vendor_id)}`}
                    </td>
                    <td>{humanize(item.status)}</td>
                    <td>{formatMinor(item.amount_minor, item.currency)}</td>
                    <td>{item.reason ?? "—"}</td>
                    <td>{formatDateTime(item.occurred_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>
    </>
  );
}
