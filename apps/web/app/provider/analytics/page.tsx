import { MarketplaceAnalytics } from "@/components/analytics/marketplace-analytics";

export const metadata = { title: "Provider analytics" };

export default function ProviderAnalyticsPage() {
  return (
    <MarketplaceAnalytics
      scope="provider"
      eyebrow="Provider analytics"
      title="Your performance"
      description="Opportunity, quote, booking, completion and response-time metrics for your provider organization only."
    />
  );
}
