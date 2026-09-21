import { ProviderRegistrationForm } from "@/components/provider/ProviderRegistrationForm";

export const metadata = { title: "Become a Provider" };

export default function BecomeProviderPage() {
  return <section className="mk-section mk-section--sky"><div className="mk-container mk-narrow"><header className="mk-heading"><p className="mk-eyebrow">Provider onboarding</p><h1>Bring your service business to BREERO.</h1><p>Apply with your business, services, coverage, and working details. Registration creates a pending application; it never activates live jobs automatically.</p></header><ProviderRegistrationForm /></div></section>;
}
