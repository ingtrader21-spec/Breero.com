"use client";

import { useCallback, useState } from "react";
import { PageHeader, useAdmin } from "../../../components/AdminShell";
import { Empty, ErrorMessage, Loading, Notice, Pager, Section, StatusBadge } from "../../../components/ui";
import { formatDateTime, formatMinor, humanize, shortId } from "../../../lib/format";
import { useResource } from "../../../lib/useResource";

const PAYMENT_STATUSES = ["created", "requires_action", "authorized", "captured", "failed", "canceled", "refunded", "partially_refunded"];
const REFUND_STATUSES = ["pending", "succeeded", "failed", "canceled"];
const PAGE_SIZE = 25;

export default function PaymentsPage() {
  const { api } = useAdmin();
  const [paymentStatus, setPaymentStatus] = useState("");
  const [paymentPage, setPaymentPage] = useState(1);
  const [refundStatus, setRefundStatus] = useState("");
  const [refundPage, setRefundPage] = useState(1);
  const finance = useResource(useCallback(() => api.financeStatus(), [api]));
  const payments = useResource(useCallback(
    () => api.listPayments({ status: paymentStatus || undefined, page: paymentPage, page_size: PAGE_SIZE }),
    [api, paymentStatus, paymentPage],
  ));
  const refunds = useResource(useCallback(
    () => api.listRefunds({ status: refundStatus || undefined, page: refundPage, page_size: PAGE_SIZE }),
    [api, refundStatus, refundPage],
  ));
  const refundCommands = finance.data?.capabilities.refund_commands;

  return (
    <>
      <PageHeader eyebrow="Finance" title="Payments & refunds" />
      <Notice tone="warning" title="Read-only inventory">
        Refund issuance and payment capture are {refundCommands === "NOT_IMPLEMENTED" || !refundCommands ? "not implemented" : humanize(refundCommands).toLowerCase()} on the finance surface.
        This page lists persisted records only and exposes no money-moving controls.
      </Notice>
      {finance.data && !finance.data.payments_enabled && (
        <Notice>Online payments are disabled for this environment, so new payment records are not expected.</Notice>
      )}
      <Section
        title="Payments"
        actions={(
          <label className="admin-form">Status
            <select value={paymentStatus} onChange={(event) => { setPaymentPage(1); setPaymentStatus(event.target.value); }}>
              <option value="">All</option>
              {PAYMENT_STATUSES.map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
            </select>
          </label>
        )}
      >
        <Loading active={payments.loading} />
        <ErrorMessage error={payments.error} />
        {payments.data && payments.data.items.length === 0 && <Empty>No payments recorded.</Empty>}
        {payments.data && payments.data.items.length > 0 && (
          <>
            <div className="portal-table-wrap">
              <table>
                <thead><tr><th>Payment</th><th>Purpose</th><th>Status</th><th>Amount</th><th>Captured</th><th>Created</th></tr></thead>
                <tbody>
                  {payments.data.items.map((payment) => (
                    <tr key={payment.id}>
                      <td>{shortId(payment.id)}</td>
                      <td>{humanize(payment.payment_purpose)}</td>
                      <td><StatusBadge value={payment.status} tone={payment.status === "failed" ? "danger" : payment.status === "captured" ? "success" : "neutral"} /></td>
                      <td>{formatMinor(payment.amount_minor, payment.currency.toUpperCase())}</td>
                      <td>{formatMinor(payment.captured_amount_minor, payment.currency.toUpperCase())}</td>
                      <td>{formatDateTime(payment.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager page={payments.data.page} pageSize={payments.data.page_size} total={payments.data.total} onPage={setPaymentPage} />
          </>
        )}
      </Section>
      <Section
        title="Refunds"
        actions={(
          <label className="admin-form">Status
            <select value={refundStatus} onChange={(event) => { setRefundPage(1); setRefundStatus(event.target.value); }}>
              <option value="">All</option>
              {REFUND_STATUSES.map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
            </select>
          </label>
        )}
      >
        <Loading active={refunds.loading} />
        <ErrorMessage error={refunds.error} />
        {refunds.data && refunds.data.items.length === 0 && <Empty>No refunds recorded.</Empty>}
        {refunds.data && refunds.data.items.length > 0 && (
          <>
            <div className="portal-table-wrap">
              <table>
                <thead><tr><th>Refund</th><th>Payment</th><th>Status</th><th>Amount (minor)</th><th>Reason</th><th>Created</th></tr></thead>
                <tbody>
                  {refunds.data.items.map((refund) => (
                    <tr key={refund.id}>
                      <td>{shortId(refund.id)}</td>
                      <td>{shortId(refund.payment_id)}</td>
                      <td>{humanize(refund.status)}</td>
                      <td>{refund.amount_minor}</td>
                      <td>{refund.reason ?? "—"}</td>
                      <td>{formatDateTime(refund.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager page={refunds.data.page} pageSize={refunds.data.page_size} total={refunds.data.total} onPage={setRefundPage} />
          </>
        )}
      </Section>
    </>
  );
}
