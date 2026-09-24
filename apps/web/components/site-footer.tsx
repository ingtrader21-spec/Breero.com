import { ArrowRightIcon, ShieldIcon } from "@breero/ui";
import Link from "next/link";
import { legalAddress, legalBusiness, legalIdentity } from "@/content/legal";
import { breeroDomains, codestraProductNetwork } from "@/content/domains";
import { Logo } from "./brand/Logo";

const groups = [
  { title: "Services", links: [["All services", "/services"], ["Plumbing", "/services/plumbing"], ["Electrical", "/services/electrical"], ["Cleaning", "/services/cleaning"]] },
  { title: "Customer support", links: [["Request service", "/request-service"], ["Help centre", "/help"], ["Contact", "/contact"], ["Refund, rescheduling & cancellation", "/refund-cancellation"], ["Service fulfillment", "/service-fulfillment"], ["Accessibility", "/accessibility"]] },
  { title: "Company", links: [["About", "/about"], ["How it works", "/how-it-works"], ["Careers", "/careers"], ["Press", "/press"]] },
  { title: "Privacy & communications", links: [["Privacy", "/privacy"], ["Privacy choices", "/privacy-choices"], ["Terms", "/terms"], ["Cookie notice", "/cookies"], ["Cookie preferences", "/cookie-preferences"], ["Communication preferences", "/communications-preferences"], ["SMS terms", "/sms-terms"]] },
  { title: "Professionals", links: [["Partner information", "/partners"], ["Provider terms", "/provider-terms"], ["Lead terms", "/lead-terms"], ["Partner interest", "/partners#interest"]] },
] as const;

export function SiteFooter() {
  return (
    <footer className="site-footer hz-site-footer">
      <div className="hz-container">
        <section className="enterprise-footer-cta" aria-labelledby="enterprise-footer-heading">
          <div>
            <p className="enterprise-footer-cta__eyebrow">Home services, handled</p>
            <h2 id="enterprise-footer-heading">One clear next step for your home.</h2>
            <p>Tell BREERO what you need. We coordinate the request, verify the applicable provider requirements, and keep the experience clear from intake through fulfillment.</p>
          </div>
          <div className="enterprise-footer-cta__actions">
            <Link className="br-button br-button--primary br-button--lg hz-button hz-button--primary" href="/request-service" data-cta="footer-request-service">
              Request service <ArrowRightIcon size={18} />
            </Link>
            <Link className="br-button br-button--outline br-button--lg hz-button hz-button--secondary" href="/services">Explore services</Link>
          </div>
        </section>

        <div className="footer__inner hz-site-footer__grid">
          <section className="footer__intro hz-site-footer__intro" aria-labelledby="breero-footer-title">
            <Logo light />
            <p className="hz-eyebrow">Codestra product network</p>
            <h2 id="breero-footer-title" className="hz-site-footer__title">Clear home-service support, from request onward.</h2>
            <span className="footer__trust"><ShieldIcon size={18} />Request and quote workflow. No online payment is required or collected.</span>
            <p className="hz-site-footer__legal-address">
              <strong>{legalIdentity}</strong><br />
              {legalAddress}<br />
              <a href={`mailto:${legalBusiness.supportEmail}`}>{legalBusiness.supportEmail}</a><br />
              <a href={legalBusiness.corporateSite}>Codestra.co</a>
            </p>
            <div className="hz-domain-list" aria-label="Breero domains">
              <a className="hz-domain-chip" href={breeroDomains.public}>breero.com</a>
              <a className="hz-domain-chip" href={breeroDomains.partners}>partners.breero.com</a>
              <a className="hz-domain-chip" href={breeroDomains.operations}>ops.breero.com</a>
              <a className="hz-domain-chip" href={breeroDomains.administration}>admin.breero.com</a>
            </div>
          </section>

          {groups.map((group) => (
            <nav key={group.title} aria-label={`${group.title} links`}>
              <h3 className="hz-site-footer__heading">{group.title}</h3>
              <ul className="hz-site-footer__links">
                {group.links.map(([label, href]) => (
                  <li key={href}><Link className="hz-site-footer__link" href={href}>{label}</Link></li>
                ))}
              </ul>
            </nav>
          ))}
        </div>

        <div className="hz-site-footer__bottom">
          <span>© {new Date().getFullYear()} {legalIdentity}.</span>
          <div className="hz-footer-legal" aria-label="Codestra product network">
            {codestraProductNetwork.map((product) => (
              <a className="hz-site-footer__link" key={product.href} href={product.href}>{product.label}</a>
            ))}
          </div>
        </div>
      </div>
    </footer>
  );
}
