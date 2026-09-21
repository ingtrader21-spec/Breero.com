import { BookingWizard } from "@/components/booking/BookingWizard";

export default function BookingPage() {
  return <section className="mk-section mk-section--sky"><div className="mk-container mk-narrow"><header className="mk-heading"><p className="mk-eyebrow">Book a service</p><h1>Choose a time that works at your home.</h1><p>BREERO validates the service address, local timezone, coverage, provider availability, and capacity before holding a slot.</p></header><BookingWizard /></div></section>;
}
