"use client";

import { type FormEvent, useEffect, useId, useRef, useState } from "react";
import type { PublicCapabilities } from "@breero/types";
import { intakeServices } from "@/content/services";
import {
  endpointForSubmission,
  prepareSubmissionAttempt,
  PublicSubmissionError,
  stableSerialize,
  submissionErrorFromResponse,
  type PublicSubmissionKind,
  type SubmissionAttempt,
} from "@/lib/public-submissions";

type Service = { id: string; slug: string; name: string; is_active?: boolean };
type AddressValidation = { serviceable: boolean; formatted_address: string };
type SubmissionAccepted = { request_id?: string; status?: string; downstream_status?: string };
type FormState = "idle" | "sending" | "accepted" | "unserviceable" | "error";

const fallbackServices: Service[] = intakeServices.map((service) => ({
  id: `catalog-${service.slug}`,
  ...service,
  is_active: true,
}));

const US_STATES = [
  "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI",
  "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN",
  "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH",
  "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA",
  "WV", "WI", "WY",
] as const;

const TRANSACTIONAL_SMS_DISCLOSURE =
  "I agree to receive recurring automated appointment and service-status text messages from BREERO at the number provided. Message frequency varies. Message and data rates may apply. Reply STOP to opt out or HELP for help. Consent is not a condition of purchase.";
const MARKETING_SMS_DISCLOSURE =
  "I agree to receive recurring automated promotional and marketing text messages from BREERO at the number provided. Message frequency varies. Message and data rates may apply. Reply STOP to opt out or HELP for help. Consent is not a condition of purchase. Marketing SMS is currently disabled.";

function value(data: FormData, key: string): string {
  return String(data.get(key) ?? "").trim();
}

function cleanServices(items: Service[]): Service[] {
  const unique = new Map<string, Service>();
  for (const item of items) {
    if (item.is_active !== false && item.slug && item.name && !unique.has(item.slug)) {
      unique.set(item.slug, item);
    }
  }
  return [...unique.values()];
}

function StateSelect() {
  return (
    <select name="state" required autoComplete="address-level1">
      <option value="">Select state</option>
      {US_STATES.map((code) => <option key={code} value={code}>{code}</option>)}
    </select>
  );
}

function ConsentFields() {
  return (
    <>
      <label>
        <input name="transactional_contact_allowed" type="checkbox" required />
        {" "}I agree that BREERO may contact me about this request. I understand this is not a confirmed appointment.
      </label>
      <fieldset>
        <legend>Optional communications</legend>
        <label>
          <input name="transactional_email_consent" type="checkbox" />
          {" "}I agree to receive appointment and service-status email from BREERO.
        </label>
        <label>
          <input name="transactional_sms_consent" type="checkbox" />
          {" "}{TRANSACTIONAL_SMS_DISCLOSURE} See <a href="/sms-terms">SMS Terms</a> and <a href="/privacy">Privacy Policy</a>.
        </label>
        <label>
          <input name="marketing_email_consent" type="checkbox" />
          {" "}I separately agree to marketing email. Marketing email is currently disabled.
        </label>
        <label>
          <input name="marketing_sms_consent" type="checkbox" />
          {" "}{MARKETING_SMS_DISCLOSURE} See <a href="/sms-terms">SMS Terms</a> and <a href="/privacy">Privacy Policy</a>.
        </label>
      </fieldset>
    </>
  );
}

function submitLabel(kind: PublicSubmissionKind): string {
  if (kind === "service") return "Request service";
  if (kind === "provider") return "Submit partner interest";
  return "Send message";
}

export function PublicIntakeForm({ kind }: { kind: PublicSubmissionKind }) {
  const formRef = useRef<HTMLFormElement>(null);
  const errorPrefix = useId();
  const needsCatalog = kind !== "contact";
  const [services, setServices] = useState<Service[]>(needsCatalog ? fallbackServices : []);
  const [catalogError, setCatalogError] = useState(false);
  const [catalogEmpty, setCatalogEmpty] = useState(false);
  const [capabilitiesError, setCapabilitiesError] = useState(false);
  const [capabilities, setCapabilities] = useState<PublicCapabilities | null>(null);
  const [state, setState] = useState<FormState>("idle");
  const [submissionError, setSubmissionError] = useState<PublicSubmissionError | null>(null);
  const [reference, setReference] = useState<string | null>(null);
  const attemptRef = useRef<SubmissionAttempt | null>(null);
  const consentTimestampRef = useRef<string | null>(null);

  useEffect(() => {
    setCatalogError(false);
    setCatalogEmpty(false);
    setCapabilitiesError(false);
    setServices(kind === "contact" ? [] : fallbackServices);
    setCapabilities(null);
    if (kind === "contact") return;

    const controller = new AbortController();
    fetch("/api/services", { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("catalog unavailable");
        return response.json() as Promise<Service[]>;
      })
      .then((items) => {
        const cleaned = cleanServices(items);
        if (cleaned.length) {
          setServices(cleaned);
        } else {
          setServices([]);
          setCatalogEmpty(true);
        }
      })
      .catch((error: unknown) => {
        if ((error as { name?: string }).name !== "AbortError") setCatalogError(true);
      });

    if (kind === "service") {
      fetch("/api/capabilities", { signal: controller.signal })
        .then((response) => {
          if (!response.ok) throw new Error("capabilities unavailable");
          return response.json() as Promise<PublicCapabilities>;
        })
        .then(setCapabilities)
        .catch((error: unknown) => {
          if ((error as { name?: string }).name !== "AbortError") setCapabilitiesError(true);
        });
    }

    return () => controller.abort();
  }, [kind]);

  function clearTransientFeedback() {
    if (state === "error" || state === "unserviceable") setState("idle");
    setSubmissionError(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (state === "sending") return;
    if (kind === "service" && !capabilities?.request_intake) {
      setSubmissionError(new PublicSubmissionError(
        "Service requests are temporarily unavailable. Please try again shortly.",
        { status: 503 },
      ));
      setState("error");
      return;
    }

    const form = event.currentTarget;
    const data = new FormData(form);
    const source = new URL(window.location.href);
    setState("sending");
    setSubmissionError(null);
    setReference(null);

    const shared = {
      source_url: window.location.href,
      company: value(data, "company"),
      utm_source: source.searchParams.get("utm_source") ?? undefined,
      utm_medium: source.searchParams.get("utm_medium") ?? undefined,
      utm_campaign: source.searchParams.get("utm_campaign") ?? undefined,
      utm_content: source.searchParams.get("utm_content") ?? undefined,
      utm_term: source.searchParams.get("utm_term") ?? undefined,
      customer_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      transactional_contact_allowed: data.get("transactional_contact_allowed") === "on",
      transactional_email_consent: data.get("transactional_email_consent") === "on",
      transactional_sms_consent: data.get("transactional_sms_consent") === "on",
      marketing_email_consent: data.get("marketing_email_consent") === "on",
      marketing_sms_consent: data.get("marketing_sms_consent") === "on",
      consent_disclosures: {
        transactional_sms: TRANSACTIONAL_SMS_DISCLOSURE,
        marketing_sms: MARKETING_SMS_DISCLOSURE,
      },
      marketing_consent: false,
      sms_consent: false,
      email_consent: false,
      consent_source: "breero_public_intake",
      policy_version: "2026-08-13-request-only",
    };

    const payloadWithoutTimestamp = kind === "service"
      ? {
          ...shared,
          name: value(data, "name"),
          email: value(data, "email"),
          phone: value(data, "phone"),
          service_slug: value(data, "service_slug"),
          service_description: value(data, "message"),
          address_line1: value(data, "address_line1"),
          city: value(data, "city"),
          state: value(data, "state"),
          postal_code: value(data, "postal_code"),
          requested_date: value(data, "requested_date") || undefined,
          requested_timing: value(data, "requested_time") || undefined,
          contact_preference: value(data, "contact_preference"),
        }
      : kind === "contact"
        ? {
            ...shared,
            name: value(data, "name"),
            email: value(data, "email"),
            phone: value(data, "phone") || undefined,
            category: value(data, "category"),
            subject: value(data, "subject"),
            message: value(data, "message"),
          }
        : {
            ...shared,
            business_name: value(data, "business_name"),
            contact_name: value(data, "contact_name"),
            email: value(data, "email"),
            phone: value(data, "phone"),
            business_website: value(data, "business_website") || undefined,
            service_categories: [value(data, "service_category")],
            city: value(data, "city"),
            state: value(data, "state"),
            postal_code: value(data, "postal_code"),
            license_details: value(data, "license_details") || undefined,
            notes: value(data, "message") || undefined,
          };

    try {
      if (kind === "service") {
        const address = [
          value(data, "address_line1"),
          value(data, "city"),
          value(data, "state"),
          value(data, "postal_code"),
          "US",
        ].join(", ");
        const validation = await fetch("/api/addresses/validate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ address }),
        }).catch(() => null);

        // The request-only release permits operator validation when geocoding is disabled.
        if (validation?.ok) {
          const result = await validation.json() as AddressValidation;
          if (!result.serviceable) {
            setState("unserviceable");
            return;
          }
        }
      }

      const previousAttempt = attemptRef.current;
      const attempt = prepareSubmissionAttempt(previousAttempt, payloadWithoutTimestamp);
      if (attempt !== previousAttempt) consentTimestampRef.current = new Date().toISOString();
      attemptRef.current = attempt;
      const payload = {
        ...payloadWithoutTimestamp,
        consent_timestamp: consentTimestampRef.current,
      };

      const response = await fetch(`/api/public-submissions/${endpointForSubmission(kind)}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": attempt.idempotencyKey,
        },
        body: stableSerialize(payload),
      });
      if (!response.ok) throw await submissionErrorFromResponse(response);

      const accepted = await response.json() as SubmissionAccepted;
      setReference(
        accepted.request_id
        ?? response.headers.get("x-correlation-id")
        ?? response.headers.get("x-request-id"),
      );
      setState("accepted");
      attemptRef.current = null;
      consentTimestampRef.current = null;
      form.reset();
    } catch (error: unknown) {
      const normalized = error instanceof PublicSubmissionError
        ? error
        : new PublicSubmissionError(
            "BREERO could not accept the request right now. Your information is still in the form; please retry.",
            { status: 0 },
          );
      setSubmissionError(normalized);
      setReference(normalized.correlationId ?? null);
      setState("error");
    }
  }

  const catalogReady = !needsCatalog || (services.length > 0 && !catalogEmpty);
  const capabilityReady = kind !== "service"
    || (!capabilitiesError && capabilities?.request_intake === true);
  const submitDisabled = state === "sending" || !catalogReady || !capabilityReady;
  const fieldMessages = Object.entries(submissionError?.fields ?? {});
  useEffect(() => {
    const form = formRef.current;
    if (!form || !submissionError?.fields) return;
    const controls: HTMLElement[] = [];
    Object.keys(submissionError.fields).forEach((field, index) => {
      const control = form.elements.namedItem(field);
      if (control instanceof HTMLElement) {
        control.setAttribute("aria-invalid", "true");
        control.setAttribute("aria-describedby", `${errorPrefix}-${index}`);
        controls.push(control);
      }
    });
    controls[0]?.focus();
    return () => controls.forEach((control) => {
      control.removeAttribute("aria-invalid");
      control.removeAttribute("aria-describedby");
    });
  }, [submissionError, errorPrefix]);

  return (
    <form
      ref={formRef}
      className="mk-intake"
      onSubmit={submit}
      onInput={clearTransientFeedback}
      aria-busy={state === "sending"}
    >
      <div className="mk-intake__honeypot" aria-hidden="true">
        <label>Company website<input name="company" tabIndex={-1} autoComplete="off" /></label>
      </div>

      {kind === "provider" ? (
        <>
          <label>Business name<input name="business_name" required minLength={2} maxLength={200} /></label>
          <label>Contact name<input name="contact_name" required minLength={2} maxLength={160} autoComplete="name" /></label>
        </>
      ) : (
        <label>Name<input name="name" required minLength={2} maxLength={160} autoComplete="name" /></label>
      )}

      <label>Email<input name="email" type="email" required autoComplete="email" /></label>
      <label>Phone<input name="phone" type="tel" required={kind !== "contact"} minLength={7} maxLength={40} autoComplete="tel" /></label>

      {kind === "service" && (
        <>
          <label>
            Service
            <select name="service_slug" required defaultValue="" disabled={!services.length || catalogEmpty}>
              <option value="" disabled>Select a service</option>
              {services.map((service) => <option key={service.slug} value={service.slug}>{service.name}</option>)}
            </select>
          </label>
          <label>Street address<input name="address_line1" required minLength={3} maxLength={240} autoComplete="street-address" /></label>
          <label>City<input name="city" required minLength={2} maxLength={120} autoComplete="address-level2" /></label>
          <label>State or district<StateSelect /></label>
          <label>ZIP code<input name="postal_code" required pattern="[0-9]{5}(-[0-9]{4})?" autoComplete="postal-code" /></label>
          <label>Preferred date (request only)<input name="requested_date" type="date" required /></label>
          <label>Preferred local time (request only)<input name="requested_time" type="time" min="07:00" max="19:00" required /></label>
          <label>
            Contact preference
            <select name="contact_preference">
              <option value="email">Email</option>
              <option value="phone">Phone</option>
              <option value="text">Text</option>
            </select>
          </label>
        </>
      )}

      {kind === "contact" && (
        <>
          <label>
            Category
            <select name="category">
              <option value="booking_help">Request help</option>
              <option value="service_issue">Service issue</option>
              <option value="billing">Billing</option>
              <option value="general">General</option>
              <option value="business">Business</option>
              <option value="privacy_request">Privacy request</option>
              <option value="provider_question">Provider question</option>
            </select>
          </label>
          <label>Subject<input name="subject" required minLength={3} maxLength={200} /></label>
          <label>Message<textarea name="message" required minLength={10} maxLength={5000} /></label>
        </>
      )}

      {kind === "provider" && (
        <>
          <label>Website <span>(optional)</span><input name="business_website" type="url" /></label>
          <label>
            Primary service
            <select name="service_category" required defaultValue="" disabled={!services.length || catalogEmpty}>
              <option value="" disabled>Select a service</option>
              {services.map((service) => <option key={service.slug} value={service.slug}>{service.name}</option>)}
            </select>
          </label>
          <label>City<input name="city" required minLength={2} maxLength={120} autoComplete="address-level2" /></label>
          <label>State or district<StateSelect /></label>
          <label>ZIP code<input name="postal_code" required pattern="[0-9]{5}(-[0-9]{4})?" autoComplete="postal-code" /></label>
          <label>License information <span>(when applicable)</span><input name="license_details" maxLength={1000} /></label>
        </>
      )}

      {(kind === "service" || kind === "provider") && (
        <label>
          {kind === "service" ? "What do you need help with?" : "Anything else we should know?"}
          <textarea
            name="message"
            required={kind === "service"}
            minLength={kind === "service" ? 5 : undefined}
            maxLength={kind === "service" ? 4000 : 3000}
          />
        </label>
      )}

      <ConsentFields />

      <p className="mk-intake__disclosure">
        BREERO coordinates requests with independent service providers. Providers remain responsible for final estimates, scope, pricing, licensing, permits, insurance, workmanship and service performance.
      </p>

      {catalogError && needsCatalog && (
        <p className="mk-intake__notice" role="status">
          We could not refresh the live catalog, so the standard service list is shown. You can still send your request.
        </p>
      )}
      {catalogEmpty && needsCatalog && (
        <p role="alert">
          No services are currently accepting requests. Please check back later or contact support@breero.com.
        </p>
      )}
      {kind === "service" && capabilitiesError && (
        <p role="alert">
          Request availability could not be verified. Please retry or contact support@breero.com.
        </p>
      )}
      {kind === "service" && capabilities && !capabilities.request_intake && (
        <p role="alert">Service request intake is temporarily unavailable.</p>
      )}

      <button className="mk-button mk-button--primary" type="submit" disabled={submitDisabled}>
        {state === "sending" ? "Sending…" : submitLabel(kind)}
      </button>

      <div aria-live="polite">
        {state === "accepted" && (
          <p className="mk-intake__success">
            Your request was accepted for review. This is not an appointment, provider assignment, final price or payment confirmation.
            {reference && <> Reference: <strong>{reference}</strong>.</>}
          </p>
        )}
        {state === "unserviceable" && (
          <p role="alert">
            We could not confirm service coverage for that address. Check the address and ZIP code, or contact support@breero.com.
          </p>
        )}
        {state === "error" && submissionError && (
          <div role="alert">
            <p>{submissionError.message}</p>
            {submissionError.retryAfterSeconds !== undefined && (
              <p>Retry after approximately {submissionError.retryAfterSeconds} seconds.</p>
            )}
            {fieldMessages.length > 0 && (
              <ul>{fieldMessages.map(([field, messages], index) => <li id={`${errorPrefix}-${index}`} key={field}>{field.replaceAll("_", " ")}: {messages.join(". ")}</li>)}</ul>
            )}
            {reference && <p>Support reference: <strong>{reference}</strong>.</p>}
          </div>
        )}
      </div>
    </form>
  );
}
