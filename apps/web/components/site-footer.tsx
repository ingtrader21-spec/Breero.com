import { ArrowRightIcon, ShieldIcon } from "@breero/ui";
import Link from "next/link";
import { legalAddress, legalBusiness, legalIdentity } from "@/content/legal";
import { Logo } from "./brand/Logo";

const groups = [
  { title: "Services", links: [["All services", "/services"], ["Plumbing", "/services/plumbing"], ["Electrical", "/services/electrical"], ["Cleaning", "/services/cleaning"]] },
  { title: "Company", links: [["About", "/about"], ["How it works", "/how-it-works"], ["Careers", "/careers"], ["Press", "/press"]] },
  { title: "Support", links: [["Request service", "/request-service"], ["Help centre", "/help"], ["Contact", "/contact"], ["Refund, rescheduling & cancellation", "/refund-cancellation"], ["Service fulfillment", "/service-fulfillment"]] },
  { title: "Privacy & communications", links: [["Privacy choices", "/privacy-choices"], ["Cookie notice", "/cookies"], ["Cookie preferences", "/cookie-preferences"], ["Communication preferences", "/communications-preferences"], ["SMS terms", "/sms-terms"]] },
  { title: "Professionals", links: [["Partner information", "/partners"], ["Provider terms", "/provider-terms"], ["Lead terms", "/lead-terms"], ["Partner interest", "/partners#interest"]] },
];

export function SiteFooter() {
  return <footer className="site-footer">
    <section className="enterprise-footer-cta" aria-labelledby="enterprise-footer-heading">
      <div>
        <p className="enterprise-footer-cta__eyebrow">Home services, handled</p>
        <h2 id="enterprise-footer-heading">One clear next step for your home.</h2>
        <p>Tell BREERO what you need. We coordinate the request, verify the applicable provider requirements, and keep the experience clear from intake through fulfillment.</p>
      </div>
      <div className="enterprise-footer-cta__actions">
        <Link className="br-button br-button--primary br-button--lg" href="/request-service" data-cta="footer-request-service">Request service <ArrowRightIcon size={18} /></Link>
        <Link className="br-button br-button--outline br-button--lg" href="/services">Explore services</Link>
      </div>
    </section>
    <div className="footer__inner">
      <div className="footer__intro">
        <Logo light />
        <p>Home services, without the hassle.</p>
        <span className="footer__trust"><ShieldIcon size={18} />Request and quote workflow. No online payment is required or collected.</span>
        <p><strong>{legalIdentity}</strong><br/>{legalAddress}<br/><a href={`mailto:${legalBusiness.supportEmail}`}>{legalBusiness.supportEmail}</a><br/><a href={legalBusiness.corporateSite}>Codestra.co</a></p>
      </div>
      <div className="footer__links">
        {groups.map((group) => <div key={group.title}><h2>{group.title}</h2>{group.links.map(([label, href]) => <Link key={href} href={href}>{label}</Link>)}</div>)}
      </div>
    </div>
    <div className="footer__legal">
      <span>© {new Date().getFullYear()} {legalIdentity}.</span>
      <div><Link href="/privacy">Privacy</Link><Link href="/privacy-choices">Privacy choices</Link><Link href="/terms">Terms</Link><Link href="/service-fulfillment">Fulfillment</Link><Link href="/cookies">Cookies</Link><Link href="/accessibility">Accessibility</Link></div>
    </div>
  </footer>;
}
