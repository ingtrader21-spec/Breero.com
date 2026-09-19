import type { BreeroApi } from "./client";
import type {
  AccessCatalog, AddressValidation, AuthSession, AvailabilitySlot, Booking, BookingCreateResponse,
  CustomerProfile, EmailCredential, EmailDomain, EmailOutboxEntry, EmailSender, LoginMode, Payment,
  PortalContext, PublicCapabilities, Quote, ServiceDetail, ServiceSummary, TenantEmailMessage, User,
} from "@breero/types";

export interface MockScenario {
  services?: ServiceDetail[]; address?: AddressValidation; slots?: AvailabilitySlot[];
  session?: AuthSession; bookings?: Booking[]; bookingCreateResponse?: BookingCreateResponse; payments?: Payment[]; quotes?: Quote[]; profile?: CustomerProfile;
  capabilities?: PublicCapabilities; portalContext?: PortalContext; loginMode?: LoginMode; accessCatalog?: AccessCatalog;
  emailDomains?: EmailDomain[]; emailSenders?: EmailSender[]; emailCredentials?: EmailCredential[];
  emailMessages?: TenantEmailMessage[]; emailOutbox?: EmailOutboxEntry[];
  latencyMs?: number; fail?: Partial<Record<keyof BreeroApi, Error>>;
}
const wait = (ms: number, signal?: AbortSignal) => new Promise<void>((resolve, reject) => {
  if (signal?.aborted) return reject(signal.reason);
  const id = setTimeout(resolve, ms);
  signal?.addEventListener("abort", () => { clearTimeout(id); reject(signal.reason); }, { once: true });
});
const missing = (name: string): never => { throw new Error(`Mock scenario is missing ${name}`); };
const now = () => new Date().toISOString();
const id = (prefix: string) => `${prefix}-${Math.random().toString(36).slice(2, 10)}`;

const defaultCatalog: AccessCatalog = {
  roles: ["customer", "vendor_admin", "technician", "operations", "ops_manager", "support", "finance", "quality", "trust_safety", "sales", "marketing", "admin", "superadmin"],
  departments: ["customer", "provider", "field_service", "dispatch", "customer_support", "vendor_success", "finance", "quality", "trust_safety", "sales", "marketing", "administration"],
  tenant_scopes: ["global", "brand", "vendor"],
};

export function createMockBreeroApi(scenario: MockScenario = {}): BreeroApi {
  let profile = scenario.profile;
  let portalContext = scenario.portalContext;
  const domains = [...(scenario.emailDomains ?? [])];
  const senders = [...(scenario.emailSenders ?? [])];
  const credentials = [...(scenario.emailCredentials ?? [])];
  const messages = [...(scenario.emailMessages ?? [])];
  const outbox = [...(scenario.emailOutbox ?? [])];
  const run = async <T>(domain: keyof BreeroApi, value: () => T, signal?: AbortSignal): Promise<T> => {
    await wait(scenario.latencyMs ?? 0, signal);
    if (scenario.fail?.[domain]) throw scenario.fail[domain];
    return value();
  };
  const defaultPortalContext = (): PortalContext => {
    const user = scenario.session?.user ?? missing("session.user");
    return {
      user,
      brand_key: "breero",
      dashboard_path: "/account",
      roles: ["customer"],
      departments: ["customer"],
      permissions: ["customer.profile.read", "customer.booking.read", "customer.quote.read"],
      assignments: [{ role: "customer", department: "customer", tenant_scope: "brand", vendor_id: null, is_primary: true }],
      identity_mode: scenario.loginMode?.mode ?? "local",
    };
  };
  return {
    public: { capabilities: (s) => run("public", () => scenario.capabilities ?? {
      request_intake: true, instant_booking: false, online_payments: false,
      automatic_assignment: false, provider_self_service: false,
      marketplace_matching: false, messaging: false, reviews: false,
    }, s) },
    auth: {
      loginMode: (s) => run("auth", () => scenario.loginMode ?? { mode: "local", issuer: "" }, s),
      login: () => run("auth", () => scenario.session ?? missing("session")),
      register: () => run("auth", () => scenario.session ?? missing("session")),
      refresh: () => run("auth", () => scenario.session ?? missing("session")),
      logout: () => run("auth", () => undefined),
      logoutAll: (s) => run("auth", () => undefined, s),
      forgotPassword: () => run("auth", () => ({ message: "If the account exists, reset instructions have been sent" })),
      resetPassword: () => run("auth", () => ({ message: "Password reset" })),
      changePassword: () => run("auth", () => ({ message: "Password changed; active sessions revoked" })),
      verifyEmail: () => run("auth", () => ({ message: "Email verified" })),
      resendVerification: (s) => run("auth", () => ({ message: "Verification sent if required" }), s),
      me: (s) => run<User>("auth", () => scenario.session?.user ?? missing("session.user"), s),
      context: (s) => run("auth", () => portalContext ?? defaultPortalContext(), s),
      accessCatalog: (s) => run("auth", () => scenario.accessCatalog ?? defaultCatalog, s),
      userAccess: (_userId, s) => run("auth", () => portalContext ?? defaultPortalContext(), s),
      replaceUserAccess: (_userId, input, s) => run("auth", () => {
        const current = portalContext ?? defaultPortalContext();
        const assignments = input.assignments.map((item) => ({
          role: item.role, department: item.department, tenant_scope: item.tenant_scope,
          vendor_id: item.vendor_id ?? null, is_primary: item.is_primary ?? false,
        }));
        portalContext = {
          ...current,
          brand_key: input.brand_key ?? current.brand_key,
          roles: [...new Set(assignments.map((item) => item.role))],
          departments: [...new Set(assignments.map((item) => item.department))],
          assignments,
        };
        return portalContext;
      }, s),
    },
    email: {
      domains: (s) => run("email", () => [...domains], s),
      createDomain: (input, s) => run("email", () => {
        const record: EmailDomain = {
          id: id("domain"), brand_key: input.brand_key ?? "breero", vendor_id: input.vendor_id ?? null,
          domain: input.domain, verification_status: "PENDING", dkim_selector: input.dkim_selector ?? null,
          return_path_domain: input.return_path_domain ?? null, active: true, created_at: now(),
        };
        domains.push(record); return record;
      }, s),
      setDomainVerification: (domainId, verified, s) => run("email", () => {
        const record = domains.find((item) => item.id === domainId) ?? missing(`email domain ${domainId}`);
        record.verification_status = verified ? "VERIFIED" : "PENDING"; return record;
      }, s),
      senders: (s) => run("email", () => [...senders], s),
      createSender: (input, s) => run("email", () => {
        const record: EmailSender = {
          id: id("sender"), brand_key: input.brand_key ?? "breero", vendor_id: input.vendor_id ?? null,
          domain_id: input.domain_id, local_part: input.local_part, display_name: input.display_name,
          reply_to: input.reply_to ?? null, active: true, created_at: now(),
        };
        senders.push(record); return record;
      }, s),
      credentials: (s) => run("email", () => [...credentials], s),
      createCredential: (input, s) => run("email", () => {
        const record: EmailCredential = {
          id: id("credential"), brand_key: input.brand_key ?? "breero", vendor_id: input.vendor_id ?? null,
          provider: input.provider, label: input.label, username: input.username ?? null,
          smtp_host: input.smtp_host ?? null, smtp_port: input.smtp_port ?? null, use_tls: input.use_tls ?? true,
          active: true, secret_configured: Boolean(input.secret_ref), created_at: now(),
        };
        credentials.push(record); return record;
      }, s),
      compose: (input, s) => run("email", () => {
        const record: TenantEmailMessage = {
          id: id("message"), brand_key: input.brand_key ?? "breero", vendor_id: input.vendor_id ?? null,
          sender_id: input.sender_id, credential_id: input.credential_id, to_email: input.to_email,
          subject: input.subject, status: "QUEUED", idempotency_key: input.idempotency_key,
          queued_at: now(), delivered_at: null, provider_message_id: null, created_at: now(),
        };
        messages.push(record);
        outbox.push({ id: id("event"), message_id: record.id, status: "PENDING_CONFIGURATION", attempts: 0, next_attempt_at: now(), last_error_code: null });
        return record;
      }, s),
      message: (messageId, s) => run("email", () => messages.find((item) => item.id === messageId) ?? missing(`email message ${messageId}`), s),
      outbox: (s) => run("email", () => [...outbox], s),
      retryOutbox: (eventId, s) => run("email", () => {
        const entry = outbox.find((item) => item.id === eventId) ?? missing(`email outbox ${eventId}`);
        entry.status = "PENDING"; entry.attempts = 0; return entry;
      }, s),
    },
    services: {
      list: (s) => run<ServiceSummary[]>("services", () => scenario.services ?? [], s),
      detail: (serviceId, s) => run("services", () => scenario.services?.find((item) => item.id === serviceId) ?? missing(`service ${serviceId}`), s),
      questions: (serviceId, s) => run("services", () => scenario.services?.find((item) => item.id === serviceId)?.questions ?? missing(`service ${serviceId}`), s),
    },
    addresses: { validate: (_input, s) => run("addresses", () => scenario.address ?? missing("address"), s) },
    availability: { search: (_input, s) => run("availability", () => scenario.slots ?? [], s) },
    bookings: {
      create: (_input, _key, s) => run("bookings", () => scenario.bookingCreateResponse ?? missing("bookingCreateResponse"), s),
      prepareGuestPayment: (_bookingId, _token, _key, s) => run("payments", () => scenario.payments?.[0] ?? missing("payment"), s),
      guestConfirmation: (bookingId, _token, s) => run("bookings", () => {
        const booking = scenario.bookings?.find((item) => item.id === bookingId) ?? missing(`booking ${bookingId}`);
        const payment = scenario.payments?.find((item) => item.booking_id === bookingId);
        return { booking_id: booking.id, reference: booking.reference, booking_status: booking.status, payment_status: payment?.status ?? "not_started", window_start: booking.window_start, window_end: booking.window_end, amount_minor: Math.round(Number(booking.total_amount) * 100), currency: booking.currency, next_action: booking.status === "CONFIRMED" ? "confirmed" as const : "await_payment_confirmation" as const };
      }, s),
      mine: (_params, s) => run("bookings", () => ({ items: scenario.bookings ?? [], total: scenario.bookings?.length ?? 0, page: 1, page_size: 20 }), s),
      getMine: (bookingId, s) => run("bookings", () => scenario.bookings?.find((item) => item.id === bookingId) ?? missing(`booking ${bookingId}`), s),
      cancelMine: (bookingId, s) => run("bookings", () => ({ ...(scenario.bookings?.find((item) => item.id === bookingId) ?? missing(`booking ${bookingId}`)), status: "CANCELLED" }), s),
    },
    payments: { createIntent: (_input, _key, s) => run("payments", () => scenario.payments?.[0] ?? missing("payment"), s) },
    customer: {
      profile: (s) => run("customer", () => profile ?? missing("profile"), s),
      updateProfile: (input, s) => run("customer", () => profile = { ...(profile ?? missing("profile")), ...input }, s),
      addresses: (s) => run("customer", () => [], s),
      addAddress: (input, s) => run("customer", () => ({ id: "mock-address", ...input }), s),
      updateAddress: (addressId, input, s) => run("customer", () => ({ id: addressId, ...input }), s),
      deleteAddress: (_addressId, s) => run("customer", () => undefined, s),
      payments: (_params, s) => run("customer", () => {
        const items = (scenario.payments ?? []).map((payment) => ({
          id: payment.id, booking_id: payment.booking_id, quote_id: payment.quote_id ?? null,
          payment_purpose: payment.payment_purpose ?? "BOOKING_DIAGNOSTIC", provider: payment.provider, status: payment.status,
          amount_minor: payment.amount_minor, captured_amount_minor: payment.captured_amount_minor,
          refunded_amount_minor: payment.status === "refunded" ? payment.amount_minor : 0,
          currency: payment.currency, failure_code: payment.failure_code, created_at: payment.created_at, updated_at: payment.updated_at,
        }));
        return { items, total: items.length, page: 1, page_size: 20 };
      }, s),
      payment: (paymentId, s) => run("customer", () => {
        const payment = scenario.payments?.find((item) => item.id === paymentId) ?? missing(`payment ${paymentId}`);
        return { id: payment.id, booking_id: payment.booking_id, quote_id: payment.quote_id ?? null,
          payment_purpose: payment.payment_purpose ?? "BOOKING_DIAGNOSTIC", provider: payment.provider, status: payment.status,
          amount_minor: payment.amount_minor, captured_amount_minor: payment.captured_amount_minor,
          refunded_amount_minor: payment.status === "refunded" ? payment.amount_minor : 0,
          currency: payment.currency, failure_code: payment.failure_code, created_at: payment.created_at, updated_at: payment.updated_at };
      }, s),
    },
    quotes: {
      list: (_params, s) => run("quotes", () => ({ items: scenario.quotes ?? [], total: scenario.quotes?.length ?? 0, page: 1, page_size: 20 }), s),
      get: (quoteId, s) => run("quotes", () => scenario.quotes?.find((item) => item.id === quoteId) ?? missing(`quote ${quoteId}`), s),
      decide: (quoteId, approve, s) => run("quotes", () => ({ ...(scenario.quotes?.find((item) => item.id === quoteId) ?? missing(`quote ${quoteId}`)), status: approve ? "APPROVED" : "DECLINED" }), s),
    },
  };
}
