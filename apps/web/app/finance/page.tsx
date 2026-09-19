import { DepartmentDashboard } from "@/components/portal/department-dashboard";

export const metadata = { title: "Finance dashboard" };

const modules = [
  { title: "Ledger", description: "Financial ledger visibility.", permission: "finance.ledger.read" },
  { title: "Payments", description: "Payment records available to finance.", permission: "finance.payments.read" },
  { title: "Refunds", description: "Refund records and review state.", permission: "finance.refunds.read" },
  { title: "Payouts", description: "Provider payout records when enabled.", permission: "finance.payouts.read" },
  { title: "Reconciliation", description: "Financial reconciliation records.", permission: "finance.reconciliation.read" },
];

export default function FinanceDashboard() {
  return <DepartmentDashboard department="finance" eyebrow="Finance" title="Finance dashboard" description="Your authorized financial operations workspace." modules={modules}/>;
}
