import type { BreeroApi } from "./client";
import type { AccessCatalog, AddressValidation, AuthSession, AvailabilitySlot, Booking, BookingCreateResponse, CustomerProfile, LoginMode, Payment, PortalContext, PublicCapabilities, Quote, ServiceDetail, ServiceSummary, User } from "@breero/types";

export interface MockScenario {
  services?: ServiceDetail[]; address?: AddressValidation; slots?: AvailabilitySlot[];
  session?: AuthSession; bookings?: Booking[]; bookingCreateResponse?: BookingCreateResponse; payments?: Payment[]; quotes?: Quote[]; profile?: CustomerProfile;
  capabilities?: PublicCapabilities; portalContext?: PortalContext; loginMode?: LoginMode; accessCatalog?: AccessCatalog;
  latencyMs?: number; fail?: Partial<Record<keyof BreeroApi, Error>>;
}
const wait = (ms: number, signal?: AbortSignal) => new Promise<void>((resolve, reject) => {
  if (signal?.aborted) return reject(signal.reason);
  const id = setTimeout(resolve, ms);
  signal?.addEventListener("abort", () => { clearTimeout(id); reject(signal.reason); }, { once: true });
});
const missing = (name: string): never => { throw new Error(`Mock scenario is missing ${name}`); };

const defaultCatalog: AccessCatalog = {
  roles: ["customer", "vendor_admin", "technician", "operations", "ops_manager", "support", "finance", "quality", "trust_safety", "sales", "marketing", "admin", "superadmin"],
  departments: ["customer", "provider", "field_service", "dispatch", "customer_support", "vendor_success", "finance", "quality", "trust_safety", "sales", "marketing", "administration"],
  tenant_scopes: ["global", "brand", "vendor"],
};

export function createMockBreeroApi(scenario: MockScenario = {}): BreeroApi {
  let profile = scenario.profile;
  let portalContext = scenario.portalContext;
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
          role: item.role,
          department: item.department,
          tenant_scope: item.tenant_scope,
          vendor_id: item.vendor_id ?? null,
          is_primary: item.is_primary ?? false,
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
    services: {
      list: (s) => run<ServiceSummary[]>("services", () => scenario.services ?? [], s),
      detail: (id, s) => run("services", () => scenario.services?.find((item) => item.id === id) ?? missing(`service ${id}`), s),
      questions: (id, s) => run("services", () => scenario.services?.find((item) => item.id === id)?.questions ?? missing(`service ${id}`), s),
    },
    addresses: { validate: (_input, s) => run("addresses", () => scenario.address ?? missing("address"), s) },
    availability: { search: (_input, s) => run("availability", () => scenario.slots ?? [], s) },
    bookings: {
      create: (_input, _key, s) => run("bookings", () => scenario.bookingCreateResponse ?? missing("bookingCreateResponse"), s),
      prepareGuestPayment: (_id, _token, _key, s) => run("payments", () => scenario.payments?.[0] ?? missing("payment"), s),
      guestConfirmation: (id, _token, s) => run("bookings", () => {
        const booking = scenario.bookings?.find((item) => item.id === id) ?? missing(`booking ${id}`);
        const payment = scenario.payments?.find((item) => item.booking_id === id);
        return { booking_id: booking.id, reference: booking.reference, booking_status: booking.status, payment_status: payment?.status ?? "not_started", window_start: booking.window_start, window_end: booking.window_end, amount_minor: Math.round(Number(booking.total_amount) * 100), currency: booking.currency, next_action: booking.status === "CONFIRMED" ? "confirmed" as const : "await_payment_confirmation" as const };
      }, s),
      mine: (_params, s) => run("bookings", () => ({ items: scenario.bookings ?? [], total: scenario.bookings?.length ?? 0, page: 1, page_size: 20 }), s),
      getMine: (id, s) => run("bookings", () => scenario.bookings?.find((item) => item.id === id) ?? missing(`booking ${id}`), s),
      cancelMine: (id, s) => run("bookings", () => ({ ...(scenario.bookings?.find((item) => item.id === id) ?? missing(`booking ${id}`)), status: "CANCELLED" }), s),
    },
    payments: {
      createIntent: (_input, _key, s) => run("payments", () => scenario.payments?.[0] ?? missing("payment"), s),
    },
    customer: {
      profile: (s) => run("customer", () => profile ?? missing("profile"), s),
      updateProfile: (input, s) => run("customer", () => profile = { ...(profile ?? missing("profile")), ...input }, s),
      addresses: (s) => run("customer", () => [], s),
      addAddress: (input, s) => run("customer", () => ({ id: "mock-address", ...input }), s),
      updateAddress: (id, input, s) => run("customer", () => ({ id, ...input }), s),
      deleteAddress: (_id, s) => run("customer", () => undefined, s),
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
      payment: (id, s) => run("customer", () => {
        const payment = scenario.payments?.find((item) => item.id === id) ?? missing(`payment ${id}`);
        return { id: payment.id, booking_id: payment.booking_id, quote_id: payment.quote_id ?? null,
          payment_purpose: payment.payment_purpose ?? "BOOKING_DIAGNOSTIC", provider: payment.provider, status: payment.status,
          amount_minor: payment.amount_minor, captured_amount_minor: payment.captured_amount_minor,
          refunded_amount_minor: payment.status === "refunded" ? payment.amount_minor : 0,
          currency: payment.currency, failure_code: payment.failure_code, created_at: payment.created_at, updated_at: payment.updated_at };
      }, s),
    },
    quotes: {
      list: (_params, s) => run("quotes", () => ({ items: scenario.quotes ?? [], total: scenario.quotes?.length ?? 0, page: 1, page_size: 20 }), s),
      get: (id, s) => run("quotes", () => scenario.quotes?.find((item) => item.id === id) ?? missing(`quote ${id}`), s),
      decide: (id, approve, s) => run("quotes", () => ({ ...(scenario.quotes?.find((item) => item.id === id) ?? missing(`quote ${id}`)), status: approve ? "APPROVED" : "DECLINED" }), s),
    },
  };
}