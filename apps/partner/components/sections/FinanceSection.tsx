import { Panel } from "../ui";

/**
 * Integration point only. Provider earnings and payout history are owned by the
 * finance backend; this portal must not compute, charge, or pay anything itself.
 */
export function FinanceSection() {
  return (
    <Panel title="Earnings & payouts" description="Provider-scoped earnings and payout history.">
      <div className="portal-notice" role="status">
        Earnings and payout statements will appear here once BREERO finance publishes provider-scoped,
        privacy-reviewed read endpoints. No payment, payout, or charge actions are available in this portal.
      </div>
    </Panel>
  );
}
