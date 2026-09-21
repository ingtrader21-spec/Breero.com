"use client";

import { type ChangeEvent, type FormEvent, useMemo, useState } from "react";

import {
  DataTable,
  formatDate,
  formatLabel,
  formatMoney,
  MetricCard,
  PortalConfirmForm,
  PortalEmpty,
  PortalError,
  PortalLoading,
  PortalNotice,
  PortalSection,
  StatusBadge,
  type DataColumn,
  usePortalQuery,
  usePortalSession,
} from "@breero/portal";

import type {
  Capabilities,
  CompensationPlan,
  Earning,
  ListResponse,
  PayoutBatch,
  Vendor,
} from "./admin-types";

export function FinancePanel({
  capabilities,
  onChanged,
}: {
  capabilities: Capabilities | null;
  onChanged: () => void;
}) {
  const vendors = usePortalQuery<Vendor[]>("/finance/vendors?limit=500");
  const plans = usePortalQuery<ListResponse<CompensationPlan>>(
    "/finance/compensation-plans?limit=500",
  );
  const earnings = usePortalQuery<Earning[]>("/finance/earnings?limit=500");
  const payouts = usePortalQuery<ListResponse<PayoutBatch>>(
    "/finance/payout-batches?limit=500",
  );
  const { request, state } = usePortalSession();
  const [selectedBatchId, setSelectedBatchId] = useState("");
  const [planForm, setPlanForm] = useState({
    vendor_id: "",
    name: "",
    method: "FIXED_MINOR",
    fixed_minor: "",
    percentage_bps: "",
    currency: "USD",
    hold_days: "7",
    effective_from: "",
  });
  const [batchForm, setBatchForm] = useState({ currency: "USD", vendor_id: "" });
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const payoutEnabled = capabilities?.payouts ?? false;
  const selected = payouts.data?.items.find((item) => item.id === selectedBatchId) ?? null;
  const byCurrency = useMemo(() => {
    const result = new Map<string, { available: number; pending: number; paid: number }>();
    for (const item of earnings.data ?? []) {
      const current = result.get(item.currency) ?? { available: 0, pending: 0, paid: 0 };
      if (item.status === "AVAILABLE") current.available += item.payable_minor;
      else if (item.status === "PAID") current.paid += item.payable_minor;
      else current.pending += item.payable_minor;
      result.set(item.currency, current);
    }
    return result;
  }, [earnings.data]);
  const primary = Array.from(byCurrency.entries())[0] ?? [
    "USD",
    { available: 0, pending: 0, paid: 0 },
  ];

  async function createPlan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      await request<CompensationPlan>("/finance/compensation-plans", {
        method: "POST",
        body: JSON.stringify({
          vendor_id: planForm.vendor_id,
          name: planForm.name,
          method: planForm.method,
          fixed_minor: planForm.method === "FIXED_MINOR" ? Number(planForm.fixed_minor) : null,
          percentage_bps:
            planForm.method === "PERCENTAGE" ? Number(planForm.percentage_bps) : null,
          currency: planForm.currency.toUpperCase(),
          hold_days: Number(planForm.hold_days),
          effective_from: new Date(planForm.effective_from).toISOString(),
        }),
      });
      setMessage("Compensation plan created and audited.");
      setPlanForm({
        ...planForm,
        name: "",
        fixed_minor: "",
        percentage_bps: "",
        effective_from: "",
      });
      plans.retry();
      onChanged();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to create compensation plan");
    }
  }

  async function createBatch() {
    await request<PayoutBatch>("/finance/payout-batches", {
      method: "POST",
      body: JSON.stringify({
        currency: batchForm.currency.toUpperCase(),
        vendor_id: batchForm.vendor_id || null,
      }),
    });
    setMessage("Payout batch reviewed and created pending independent approval.");
    payouts.retry();
    earnings.retry();
    onChanged();
  }

  async function approveBatch(batch: PayoutBatch) {
    await request<PayoutBatch>(`/finance/payout-batches/${batch.id}/approve`, { method: "POST" });
    setMessage("Payout batch approved by the current actor.");
    payouts.retry();
    onChanged();
  }

  async function submitBatch(batch: PayoutBatch) {
    await request<PayoutBatch>(`/finance/payout-batches/${batch.id}/submit`, { method: "POST" });
    setMessage("Payout batch submitted through the configured payout gateway.");
    payouts.retry();
    earnings.retry();
    onChanged();
  }

  const planColumns: DataColumn<CompensationPlan>[] = [
    {
      key: "provider",
      label: "Provider",
      render: (item) =>
        vendors.data?.find((vendor) => vendor.id === item.vendor_id)?.display_name ?? item.vendor_id,
    },
    {
      key: "plan",
      label: "Plan",
      render: (item) => (
        <span>
          <strong>{item.name}</strong>
          <br />
          <small>{formatLabel(item.method)}</small>
        </span>
      ),
    },
    {
      key: "rate",
      label: "Rate",
      render: (item) =>
        item.method === "FIXED_MINOR"
          ? formatMoney(item.fixed_minor ?? 0, item.currency)
          : `${((item.percentage_bps ?? 0) / 100).toFixed(2)}%`,
    },
    { key: "hold", label: "Hold", render: (item) => `${item.hold_days} days` },
    {
      key: "active",
      label: "State",
      compact: true,
      render: (item) => <StatusBadge value={item.active ? "active" : "inactive"} />,
    },
    { key: "effective", label: "Effective", render: (item) => formatDate(item.effective_from) },
  ];
  const earningColumns: DataColumn<Earning>[] = [
    {
      key: "status",
      label: "Status",
      compact: true,
      render: (item) => <StatusBadge value={item.status} />,
    },
    {
      key: "provider",
      label: "Provider",
      render: (item) =>
        vendors.data?.find((vendor) => vendor.id === item.vendor_id)?.display_name ?? item.vendor_id,
    },
    { key: "job", label: "Job", render: (item) => <span className="portal-code">{item.job_id}</span> },
    { key: "gross", label: "Gross", render: (item) => formatMoney(item.gross_minor, item.currency) },
    { key: "fee", label: "Fee", render: (item) => formatMoney(item.fee_minor, item.currency) },
    {
      key: "payable",
      label: "Payable",
      render: (item) => <strong>{formatMoney(item.payable_minor, item.currency)}</strong>,
    },
    { key: "available", label: "Available", render: (item) => formatDate(item.available_at) },
  ];
  const payoutColumns: DataColumn<PayoutBatch>[] = [
    { key: "reference", label: "Reference", render: (item) => <strong>{item.reference}</strong> },
    {
      key: "status",
      label: "Status",
      compact: true,
      render: (item) => <StatusBadge value={item.status} />,
    },
    { key: "amount", label: "Amount", render: (item) => formatMoney(item.total_minor, item.currency) },
    { key: "earnings", label: "Earnings", render: (item) => item.earning_count },
    {
      key: "review",
      label: "Reviewer",
      render: (item) => <span className="portal-code">{item.reviewed_by ?? "Unassigned"}</span>,
    },
    {
      key: "approval",
      label: "Approver",
      render: (item) => <span className="portal-code">{item.approved_by ?? "Not approved"}</span>,
    },
    {
      key: "action",
      label: "Action",
      compact: true,
      render: (item) => (
        <button type="button" className="portal-button" onClick={() => setSelectedBatchId(item.id)}>
          Review
        </button>
      ),
    },
  ];

  return (
    <div className="portal-stack">
      {message ? (
        <PortalNotice title="Finance operation completed" tone="success">
          {message}
        </PortalNotice>
      ) : null}
      {error ? (
        <p className="portal-error" role="alert">
          {error}
        </p>
      ) : null}
      <section className="portal-metric-grid" aria-label="Finance summary">
        <MetricCard
          label="Available earnings"
          value={formatMoney(primary[1].available, primary[0])}
          detail="Eligible for review and batching"
          tone="success"
        />
        <MetricCard
          label="Pending / held"
          value={formatMoney(primary[1].pending, primary[0])}
          detail="Release policy applies"
        />
        <MetricCard
          label="Paid"
          value={formatMoney(primary[1].paid, primary[0])}
          detail="Completed provider earnings"
        />
        <MetricCard
          label="Payout execution"
          value={payoutEnabled ? "Enabled" : "Disabled"}
          detail="Runtime capability"
          tone={payoutEnabled ? "success" : "warning"}
        />
      </section>
      {!payoutEnabled ? (
        <PortalNotice title="Payout execution is disabled" tone="warning">
          Earnings, plans, and historical batches remain visible. Batch creation, approval, and
          submission stay unavailable until the production capability and payout gateway are explicitly enabled.
        </PortalNotice>
      ) : null}
      <div className="portal-split">
        <PortalSection
          title="Compensation plans"
          subtitle="Plans are effective-dated and form the immutable earning snapshot."
        >
          <form className="portal-form-grid" onSubmit={(event) => void createPlan(event)}>
            <label className="portal-form-span">
              Provider
              <select
                required
                value={planForm.vendor_id}
                onChange={(event: ChangeEvent<HTMLSelectElement>) =>
                  setPlanForm({ ...planForm, vendor_id: event.target.value })
                }
              >
                <option value="">Choose provider</option>
                {(vendors.data ?? []).map((vendor) => (
                  <option key={vendor.id} value={vendor.id}>
                    {vendor.display_name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Plan name
              <input
                required
                maxLength={160}
                value={planForm.name}
                onChange={(event: ChangeEvent<HTMLInputElement>) =>
                  setPlanForm({ ...planForm, name: event.target.value })
                }
              />
            </label>
            <label>
              Method
              <select
                value={planForm.method}
                onChange={(event: ChangeEvent<HTMLSelectElement>) =>
                  setPlanForm({ ...planForm, method: event.target.value })
                }
              >
                <option value="FIXED_MINOR">Fixed amount</option>
                <option value="PERCENTAGE">Percentage</option>
              </select>
            </label>
            {planForm.method === "FIXED_MINOR" ? (
              <label>
                Fixed minor units
                <input
                  required
                  type="number"
                  min={0}
                  value={planForm.fixed_minor}
                  onChange={(event: ChangeEvent<HTMLInputElement>) =>
                    setPlanForm({ ...planForm, fixed_minor: event.target.value })
                  }
                />
              </label>
            ) : (
              <label>
                Percentage basis points
                <input
                  required
                  type="number"
                  min={0}
                  max={10000}
                  value={planForm.percentage_bps}
                  onChange={(event: ChangeEvent<HTMLInputElement>) =>
                    setPlanForm({ ...planForm, percentage_bps: event.target.value })
                  }
                />
              </label>
            )}
            <label>
              Currency
              <input
                required
                minLength={3}
                maxLength={3}
                value={planForm.currency}
                onChange={(event: ChangeEvent<HTMLInputElement>) =>
                  setPlanForm({ ...planForm, currency: event.target.value.toUpperCase() })
                }
              />
            </label>
            <label>
              Hold days
              <input
                required
                type="number"
                min={0}
                max={365}
                value={planForm.hold_days}
                onChange={(event: ChangeEvent<HTMLInputElement>) =>
                  setPlanForm({ ...planForm, hold_days: event.target.value })
                }
              />
            </label>
            <label>
              Effective from
              <input
                required
                type="datetime-local"
                value={planForm.effective_from}
                onChange={(event: ChangeEvent<HTMLInputElement>) =>
                  setPlanForm({ ...planForm, effective_from: event.target.value })
                }
              />
            </label>
            <div className="portal-form-span">
              <button className="portal-button portal-button--primary" type="submit">
                Create compensation plan
              </button>
            </div>
          </form>
          {plans.loading ? <PortalLoading label="Loading compensation plans" /> : null}
          {plans.error ? <PortalError error={plans.error} onRetry={plans.retry} /> : null}
          {plans.data ? (
            <DataTable
              rows={plans.data.items}
              columns={planColumns}
              rowKey={(item) => item.id}
              emptyTitle="No compensation plans are configured"
            />
          ) : null}
        </PortalSection>
        <PortalSection
          title="Create payout batch"
          subtitle="The creator is recorded as reviewer and cannot approve the same batch."
        >
          <div className="portal-form-grid">
            <label>
              Currency
              <input
                required
                minLength={3}
                maxLength={3}
                value={batchForm.currency}
                onChange={(event: ChangeEvent<HTMLInputElement>) =>
                  setBatchForm({ ...batchForm, currency: event.target.value.toUpperCase() })
                }
              />
            </label>
            <label>
              Provider (optional)
              <select
                value={batchForm.vendor_id}
                onChange={(event: ChangeEvent<HTMLSelectElement>) =>
                  setBatchForm({ ...batchForm, vendor_id: event.target.value })
                }
              >
                <option value="">All eligible providers</option>
                {(vendors.data ?? []).map((vendor) => (
                  <option key={vendor.id} value={vendor.id}>
                    {vendor.display_name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <PortalConfirmForm
            title="Review eligible earnings into a batch"
            description="This locks currently available earnings in the selected currency and optional provider scope into a pending-approval batch."
            confirmLabel="Create pending-approval batch"
            disabled={!payoutEnabled}
            onConfirm={createBatch}
          />
        </PortalSection>
      </div>
      <PortalSection
        title="Immutable earning ledger"
        subtitle={`${earnings.data?.length ?? 0} earning records across providers.`}
      >
        {earnings.loading ? <PortalLoading label="Loading earnings" /> : null}
        {earnings.error ? <PortalError error={earnings.error} onRetry={earnings.retry} /> : null}
        {earnings.data ? (
          <DataTable
            rows={earnings.data}
            columns={earningColumns}
            rowKey={(item) => item.id}
            emptyTitle="No earnings are available"
          />
        ) : null}
      </PortalSection>
      <div className="portal-split">
        <PortalSection
          title="Payout batches"
          subtitle={`${payouts.data?.total ?? 0} batches across all states.`}
        >
          {payouts.loading ? <PortalLoading label="Loading payout batches" /> : null}
          {payouts.error ? <PortalError error={payouts.error} onRetry={payouts.retry} /> : null}
          {payouts.data ? (
            <DataTable
              rows={payouts.data.items}
              columns={payoutColumns}
              rowKey={(item) => item.id}
              emptyTitle="No payout batches exist"
            />
          ) : null}
        </PortalSection>
        <PortalSection
          title="Payout decision"
          subtitle="Backend separation-of-duties rules remain authoritative."
        >
          {!selected ? (
            <PortalEmpty title="Choose a payout batch" />
          ) : (
            <div className="portal-stack">
              <dl className="portal-definition-grid">
                <div><dt>Reference</dt><dd>{selected.reference}</dd></div>
                <div><dt>Status</dt><dd><StatusBadge value={selected.status} /></dd></div>
                <div><dt>Amount</dt><dd>{formatMoney(selected.total_minor, selected.currency)}</dd></div>
                <div><dt>Earnings</dt><dd>{selected.earning_count}</dd></div>
                <div><dt>Reviewer</dt><dd className="portal-code">{selected.reviewed_by ?? "—"}</dd></div>
                <div><dt>Approver</dt><dd className="portal-code">{selected.approved_by ?? "—"}</dd></div>
              </dl>
              {state.status === "authenticated" && selected.reviewed_by === state.session.user.id ? (
                <PortalNotice title="Independent approval required" tone="warning">
                  The current user reviewed this batch and cannot approve it.
                </PortalNotice>
              ) : null}
              {selected.status === "PENDING_APPROVAL" ? (
                <PortalConfirmForm
                  title="Approve payout batch"
                  description="Confirm totals and evidence. The reviewer is not permitted to approve their own batch."
                  confirmLabel="Approve batch"
                  disabled={!payoutEnabled}
                  onConfirm={() => approveBatch(selected)}
                />
              ) : null}
              {selected.status === "APPROVED" ? (
                <PortalConfirmForm
                  title="Submit payout batch"
                  description="Submission calls the configured payout gateway with a durable idempotency key. The approver cannot submit the same batch."
                  confirmLabel="Submit payout"
                  disabled={!payoutEnabled}
                  onConfirm={() => submitBatch(selected)}
                />
              ) : null}
              {selected.failure_reason ? (
                <PortalNotice title="Provider failure" tone="danger">
                  {selected.failure_reason}
                </PortalNotice>
              ) : null}
            </div>
          )}
        </PortalSection>
      </div>
    </div>
  );
}
