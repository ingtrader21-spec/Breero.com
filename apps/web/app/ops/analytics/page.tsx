import { MarketplaceAnalytics } from "@/components/analytics/marketplace-analytics";

export const metadata = { title: "Marketplace analytics" };

export default function MarketplaceAnalyticsPage() {
  return (
    <MarketplaceAnalytics
      scope="marketplace"
      eyebrow="Operations analytics"
      title="Marketplace analytics"
      description="Request-to-completion marketplace metrics read directly from the system of record. Figures without a certified source are withheld, never estimated."
    />
  );
}
