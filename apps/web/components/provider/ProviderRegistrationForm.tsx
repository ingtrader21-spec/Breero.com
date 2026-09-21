"use client";

import { FormEvent, useEffect, useState } from "react";

type Service = { slug: string; name: string };

export function ProviderRegistrationForm() {
  const [services, setServices] = useState<Service[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [complete, setComplete] = useState(false);
  const base = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api/v1").replace(/\/$/, "");
  useEffect(() => { void fetch(`${base}/services`).then((r) => r.json()).then(setServices).catch(() => setError("The service catalog is unavailable.")); }, [base]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const data = new FormData(event.currentTarget);
    const selected = data.getAll("service_slugs").map(String);
    try {
      const response = await fetch(`${base}/auth/browser/register/provider`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
        email: data.get("email"), password: data.get("password"), contact_name: data.get("contact_name"), phone: data.get("phone"), legal_name: data.get("legal_name"), display_name: data.get("display_name"), provider_type: data.get("provider_type"), business_address: data.get("business_address"), city: data.get("city"), state: data.get("state"), postal_code: data.get("postal_code"), timezone_id: data.get("timezone_id"), service_slugs: selected, service_postal_codes: String(data.get("service_postal_codes")).split(/[\s,]+/).filter(Boolean),
      }) });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.error?.message ?? body.detail ?? "Application could not be submitted.");
      setComplete(true);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Application could not be submitted."); }
    finally { setBusy(false); }
  }

  if (complete) return <div className="booking-complete" role="status"><h2>Application submitted</h2><p>Your onboarding status is PENDING. You can configure your provider workspace, but live jobs remain disabled until BREERO approval.</p><a className="mk-button mk-button--primary" href="/provider">Open provider dashboard</a></div>;
  return <form className="mk-intake" onSubmit={submit}><label>Contact name<input name="contact_name" autoComplete="name" required /></label><label>Email<input name="email" type="email" autoComplete="email" required /></label><label>Phone<input name="phone" type="tel" autoComplete="tel" required /></label><label>Password<input name="password" type="password" autoComplete="new-password" minLength={10} required /></label><label>Legal business name<input name="legal_name" required /></label><label>Display name<input name="display_name" required /></label><label>Provider type<select name="provider_type"><option value="COMPANY">Company</option><option value="INDEPENDENT">Independent professional</option></select></label><label>Business address<input name="business_address" autoComplete="street-address" required /></label><label>City<input name="city" autoComplete="address-level2" required /></label><label>State<input name="state" autoComplete="address-level1" minLength={2} maxLength={2} required /></label><label>Business ZIP<input name="postal_code" autoComplete="postal-code" pattern="[0-9]{5}(-[0-9]{4})?" required /></label><label>IANA timezone<select name="timezone_id" defaultValue="America/Chicago"><option>America/New_York</option><option>America/Chicago</option><option>America/Denver</option><option>America/Phoenix</option><option>America/Los_Angeles</option><option>America/Anchorage</option><option>Pacific/Honolulu</option></select></label><fieldset className="booking-full"><legend>BREERO services</legend>{services.map((service) => <label key={service.slug} className="booking-check"><input type="checkbox" name="service_slugs" value={service.slug} />{service.name}</label>)}</fieldset><label className="booking-full">Service ZIP codes <span>Separate multiple five-digit ZIP codes with commas.</span><textarea name="service_postal_codes" required /></label><p className="mk-intake__disclosure">Submission creates a pending provider organization and professional profile. Compliance approval, active status, and live dispatch are not granted by registration.</p>{error && <div role="alert">{error}</div>}<button className="mk-button mk-button--primary" disabled={busy}>{busy ? "Submitting…" : "Submit provider application"}</button></form>;
}
