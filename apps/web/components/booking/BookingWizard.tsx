"use client";

import { FormEvent, useEffect, useState } from "react";

type Service = { id: string; name: string; slug: string; is_bookable: boolean; quote_required: boolean };
type Slot = { start_local: string; end_local: string };
type Availability = { timezone: string; date: string; address_id: string; slots: Slot[]; reason?: string };
type Envelope<T> = { data: T | null; error: { code: string; message: string } | null };

const apiBase = () => (process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api/v1").replace(/\/$/, "");

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase()}${path}`, {
    ...init,
    credentials: "include",
    headers: { Accept: "application/json", "Content-Type": "application/json", ...init?.headers },
  });
  const body = (await response.json().catch(() => ({}))) as Envelope<T> & { detail?: string };
  if (!response.ok || body.error) throw new Error(body.error?.message ?? body.detail ?? "The request could not be completed.");
  return (body.data ?? body) as T;
}

export function BookingWizard() {
  const [bookingSession, setBookingSession] = useState("");
  const [serviceId, setServiceId] = useState("");
  const [services, setServices] = useState<Service[]>([]);
  const [availability, setAvailability] = useState<Availability | null>(null);
  const [slot, setSlot] = useState("");
  const [holdId, setHoldId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [complete, setComplete] = useState<{ reference: string; status: string } | null>(null);

  useEffect(() => {
    setBookingSession(crypto.randomUUID() + crypto.randomUUID());
    fetch(`${apiBase()}/services`, { headers: { Accept: "application/json" } })
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("Services are unavailable.")))
      .then((items: Service[]) => setServices(items.filter((item) => item.is_bookable && !item.quote_required)))
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Services are unavailable."));
  }, []);

  async function findAvailability(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setHoldId(""); setSlot("");
    const data = new FormData(event.currentTarget);
    try {
      setAvailability(await api<Availability>("/booking/availability", {
        method: "POST",
        body: JSON.stringify({
          service_id: data.get("service_id"), requested_date: data.get("requested_date"),
          emergency: data.get("emergency") === "on",
          address: { line1: data.get("line1"), line2: data.get("line2") || null, city: data.get("city"), state: data.get("state"), postal_code: data.get("postal_code") },
        }),
      }));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Availability could not be checked."); }
    finally { setBusy(false); }
  }

  async function hold(serviceId: string) {
    if (!availability || !slot) return;
    setBusy(true); setError("");
    try {
      const result = await api<{ hold_id: string }>("/booking/holds", {
        method: "POST",
        headers: { "X-Booking-Session": bookingSession, "Idempotency-Key": crypto.randomUUID() + crypto.randomUUID() },
        body: JSON.stringify({ service_id: serviceId, address_id: availability.address_id, start_local: `${availability.date}T${slot}:00`, timezone: availability.timezone }),
      });
      setHoldId(result.hold_id);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "This time is no longer available."); }
    finally { setBusy(false); }
  }

  async function submitRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const data = new FormData(event.currentTarget);
    try {
      const result = await api<{ public_reference: string; status: string; access_token?: string; refresh_token?: string }>("/booking/requests", {
        method: "POST",
        body: JSON.stringify({ hold_id: holdId, booking_session: bookingSession, customer: { first_name: data.get("first_name"), last_name: data.get("last_name"), email: data.get("email"), phone: data.get("phone") }, notes: data.get("notes") || null }),
      });
      setComplete({ reference: result.public_reference, status: result.status });
    } catch (reason) { setError(reason instanceof Error ? reason.message : "The booking request could not be submitted."); }
    finally { setBusy(false); }
  }

  if (complete) return <section className="booking-complete" role="status"><p className="mk-eyebrow">Request received</p><h2>{complete.reference}</h2><p>Status: {complete.status.replaceAll("_", " ")}. A dispatcher will review the recommended provider before assignment.</p><a className="mk-button mk-button--primary" href="/account">Open your account</a></section>;

  return <div className="booking-wizard">
    <form onSubmit={findAvailability} aria-labelledby="booking-details-title">
      <h2 id="booking-details-title">1. Service and address</h2>
      <label>Service<select name="service_id" required value={serviceId} onChange={(event) => setServiceId(event.target.value)}><option value="">Choose a service</option>{services.map((service) => <option key={service.id} value={service.id}>{service.name}</option>)}</select></label>
      <label>Address line 1<input name="line1" autoComplete="address-line1" required /></label>
      <label>Address line 2<input name="line2" autoComplete="address-line2" /></label>
      <label>City<input name="city" autoComplete="address-level2" required /></label>
      <label>State<input name="state" autoComplete="address-level1" required minLength={2} maxLength={2} /></label>
      <label>ZIP or ZIP+4<input name="postal_code" autoComplete="postal-code" required pattern="[0-9]{5}(-[0-9]{4})?" /></label>
      <label>Requested date<input name="requested_date" type="date" required min={new Date().toISOString().slice(0, 10)} /></label>
      <label className="booking-check"><input name="emergency" type="checkbox" /> Emergency service (required for eligible Sunday bookings)</label>
      <button className="mk-button mk-button--primary" disabled={busy}>{busy ? "Checking…" : "Check availability"}</button>
    </form>
    {availability && <section aria-labelledby="slot-title"><h2 id="slot-title">2. Choose a local time</h2><p>Times shown in {availability.timezone}.</p>{availability.slots.length ? <div className="booking-slots" role="radiogroup" aria-label="Available appointment times">{availability.slots.map((item) => <label key={item.start_local}><input type="radio" name="slot" value={item.start_local} checked={slot === item.start_local} onChange={() => setSlot(item.start_local)} />{item.start_local}–{item.end_local}</label>)}</div> : <p>No appointments are available on this date.</p>}<button type="button" className="mk-button mk-button--primary" disabled={!slot || !bookingSession || busy} onClick={() => void hold(serviceId)}>Hold this time for 30 minutes</button></section>}
    {holdId && <form onSubmit={submitRequest} aria-labelledby="contact-title"><h2 id="contact-title">3. Contact information</h2><label>First name<input name="first_name" autoComplete="given-name" required /></label><label>Last name<input name="last_name" autoComplete="family-name" required /></label><label>Email<input name="email" type="email" autoComplete="email" required /></label><label>Phone<input name="phone" type="tel" autoComplete="tel" required /></label><label className="booking-full">Notes<textarea name="notes" maxLength={4000} /></label><p className="booking-full">Submitting creates or reconciles your client account. This request remains awaiting manual assignment.</p><button className="mk-button mk-button--primary" disabled={busy}>{busy ? "Submitting…" : "Submit booking request"}</button></form>}
    {error && <div className="booking-error" role="alert"><strong>We couldn’t continue</strong><p>{error}</p></div>}
  </div>;
}
