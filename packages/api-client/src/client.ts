import type {
  AccessCatalog, AccessProfileUpdate, AddressValidation, AddressValidationRequest, AuthSession,
  AvailabilitySearchRequest, AvailabilitySlot, Booking, BookingConfirmation, BookingCreateRequest,
  BookingCreateResponse, ChangePasswordRequest, CustomerAddress, CustomerAddressInput,
  CustomerBookingList, CustomerPayment, CustomerProfile, CustomerProfilePatch, EmailComposeRequest,
  EmailCredential, EmailCredentialCreate, EmailDomain, EmailDomainCreate, EmailOutboxEntry,
  EmailSender, EmailSenderCreate, ForgotPasswordRequest, LoginMode, LoginRequest, MessageResponse,
  Page, Payment, PaymentIntentRequest, PortalContext, PublicCapabilities, Quote, RefreshRequest,
  RegisterRequest, ResetPasswordRequest, ServiceDetail, ServiceQuestion, ServiceSummary,
  TenantEmailMessage, TokenRequest, User, UUID,
} from "@breero/types";
import { ApiTransport, type Transport, type TransportOptions } from "./transport";

export interface PageParams { page?: number; pageSize?: number }
export interface BreeroApi {
  public: { capabilities(signal?: AbortSignal): Promise<PublicCapabilities> };
  auth: {
    loginMode(signal?: AbortSignal): Promise<LoginMode>;
    login(input: LoginRequest): Promise<AuthSession>; register(input: RegisterRequest): Promise<AuthSession>;
    refresh(input: RefreshRequest): Promise<AuthSession>; logout(input: RefreshRequest): Promise<void>;
    logoutAll(signal?: AbortSignal): Promise<void>; forgotPassword(input: ForgotPasswordRequest): Promise<MessageResponse>;
    resetPassword(input: ResetPasswordRequest): Promise<MessageResponse>; changePassword(input: ChangePasswordRequest): Promise<MessageResponse>;
    verifyEmail(input: TokenRequest): Promise<MessageResponse>; resendVerification(signal?: AbortSignal): Promise<MessageResponse>;
    me(signal?: AbortSignal): Promise<User>; context(signal?: AbortSignal): Promise<PortalContext>;
    accessCatalog(signal?: AbortSignal): Promise<AccessCatalog>;
    userAccess(userId: UUID, signal?: AbortSignal): Promise<PortalContext>;
    replaceUserAccess(userId: UUID, input: AccessProfileUpdate, signal?: AbortSignal): Promise<PortalContext>;
  };
  email: {
    domains(signal?: AbortSignal): Promise<EmailDomain[]>;
    createDomain(input: EmailDomainCreate, signal?: AbortSignal): Promise<EmailDomain>;
    setDomainVerification(id: UUID, verified: boolean, signal?: AbortSignal): Promise<EmailDomain>;
    senders(signal?: AbortSignal): Promise<EmailSender[]>;
    createSender(input: EmailSenderCreate, signal?: AbortSignal): Promise<EmailSender>;
    credentials(signal?: AbortSignal): Promise<EmailCredential[]>;
    createCredential(input: EmailCredentialCreate, signal?: AbortSignal): Promise<EmailCredential>;
    compose(input: EmailComposeRequest, signal?: AbortSignal): Promise<TenantEmailMessage>;
    message(id: UUID, signal?: AbortSignal): Promise<TenantEmailMessage>;
    outbox(signal?: AbortSignal): Promise<EmailOutboxEntry[]>;
    retryOutbox(id: UUID, signal?: AbortSignal): Promise<EmailOutboxEntry>;
  };
  services: { list(signal?: AbortSignal): Promise<ServiceSummary[]>; detail(id: UUID, signal?: AbortSignal): Promise<ServiceDetail>; questions(id: UUID, signal?: AbortSignal): Promise<ServiceQuestion[]> };
  addresses: { validate(input: AddressValidationRequest, signal?: AbortSignal): Promise<AddressValidation> };
  availability: { search(input: AvailabilitySearchRequest, signal?: AbortSignal): Promise<AvailabilitySlot[]> };
  bookings: {
    create(input: BookingCreateRequest, idempotencyKey: string, signal?: AbortSignal): Promise<BookingCreateResponse>;
    prepareGuestPayment(id: UUID, guestToken: string, idempotencyKey: string, signal?: AbortSignal): Promise<Payment>;
    guestConfirmation(id: UUID, guestToken: string, signal?: AbortSignal): Promise<BookingConfirmation>;
    mine(params?: PageParams, signal?: AbortSignal): Promise<Page<Booking> | CustomerBookingList>;
    getMine(id: UUID, signal?: AbortSignal): Promise<Booking>;
    cancelMine(id: UUID, signal?: AbortSignal): Promise<Booking>;
  };
  payments: { createIntent(input: PaymentIntentRequest, idempotencyKey: string, signal?: AbortSignal): Promise<Payment> };
  customer: {
    profile(signal?: AbortSignal): Promise<CustomerProfile>; updateProfile(input: CustomerProfilePatch, signal?: AbortSignal): Promise<CustomerProfile>;
    addresses(signal?: AbortSignal): Promise<CustomerAddress[]>; addAddress(input: CustomerAddressInput, signal?: AbortSignal): Promise<CustomerAddress>;
    updateAddress(id: UUID, input: CustomerAddressInput, signal?: AbortSignal): Promise<CustomerAddress>; deleteAddress(id: UUID, signal?: AbortSignal): Promise<void>;
    payments(params?: PageParams, signal?: AbortSignal): Promise<Page<CustomerPayment>>;
    payment(id: UUID, signal?: AbortSignal): Promise<CustomerPayment>;
  };
  quotes: { list(params?: PageParams, signal?: AbortSignal): Promise<Page<Quote>>; get(id: UUID, signal?: AbortSignal): Promise<Quote>; decide(id: UUID, approve: boolean, signal?: AbortSignal): Promise<Quote> };
}

const encoded = (value: string) => encodeURIComponent(value);
const pageQuery = ({ page = 1, pageSize = 20 }: PageParams = {}) => `?page=${page}&page_size=${pageSize}`;
export function createBreeroApi(options: TransportOptions): BreeroApi { return createApiClient(new ApiTransport(options)); }

export function createApiClient(http: Transport): BreeroApi {
  return {
    public: { capabilities: (signal) => http.request("/public/capabilities", { signal }) },
    auth: {
      loginMode: (signal) => http.request("/auth/login-mode", { signal }),
      login: (body) => http.request("/auth/login", { method: "POST", body, retry: false }),
      register: (body) => http.request("/auth/register", { method: "POST", body, retry: false }),
      refresh: (body) => http.request("/auth/refresh", { method: "POST", body, retry: false }),
      logout: (body) => http.request("/auth/logout", { method: "POST", body, retry: false }),
      logoutAll: (signal) => http.request("/auth/logout-all", { method: "POST", signal, retry: false }),
      forgotPassword: (body) => http.request("/auth/password/forgot", { method: "POST", body, retry: false }),
      resetPassword: (body) => http.request("/auth/password/reset", { method: "POST", body, retry: false }),
      changePassword: (body) => http.request("/auth/password/change", { method: "POST", body, retry: false }),
      verifyEmail: (body) => http.request("/auth/email/verify", { method: "POST", body, retry: false }),
      resendVerification: (signal) => http.request("/auth/email/resend-verification", { method: "POST", signal, retry: false }),
      me: (signal) => http.request("/auth/me", { signal }),
      context: (signal) => http.request("/auth/context", { signal }),
      accessCatalog: (signal) => http.request("/auth/access/catalog", { signal }),
      userAccess: (userId, signal) => http.request(`/auth/access/users/${encoded(userId)}`, { signal }),
      replaceUserAccess: (userId, body, signal) => http.request(`/auth/access/users/${encoded(userId)}`, { method: "PUT", body, signal, retry: false }),
    },
    email: {
      domains: (signal) => http.request("/email/domains", { signal }),
      createDomain: (body, signal) => http.request("/email/domains", { method: "POST", body, signal, retry: false }),
      setDomainVerification: (id, verified, signal) => http.request(`/email/domains/${encoded(id)}/verification?verified=${verified}`, { method: "POST", signal, retry: false }),
      senders: (signal) => http.request("/email/senders", { signal }),
      createSender: (body, signal) => http.request("/email/senders", { method: "POST", body, signal, retry: false }),
      credentials: (signal) => http.request("/email/credentials", { signal }),
      createCredential: (body, signal) => http.request("/email/credentials", { method: "POST", body, signal, retry: false }),
      compose: (body, signal) => http.request("/email/messages", { method: "POST", body, signal, retry: false }),
      message: (id, signal) => http.request(`/email/messages/${encoded(id)}`, { signal }),
      outbox: (signal) => http.request("/email/outbox", { signal }),
      retryOutbox: (id, signal) => http.request(`/email/outbox/${encoded(id)}/retry`, { method: "POST", signal, retry: false }),
    },
    services: {
      list: (signal) => http.request("/services", { signal }),
      detail: (id, signal) => http.request(`/services/${encoded(id)}`, { signal }),
      questions: (id, signal) => http.request(`/services/${encoded(id)}/questions`, { signal }),
    },
    addresses: { validate: (body, signal) => http.request("/addresses/validate", { method: "POST", body, signal, retry: false }) },
    availability: { search: (body, signal) => http.request("/availability/search", { method: "POST", body, signal, retry: false }) },
    bookings: {
      create: (body, key, signal) => http.request("/bookings", { method: "POST", body, signal, retry: false, headers: { "Idempotency-Key": key } }),
      prepareGuestPayment: (id, token, key, signal) => http.request(`/bookings/${encoded(id)}/payment`, { method: "POST", signal, retry: false, headers: { Authorization: `Bearer ${token}`, "Idempotency-Key": key } }),
      guestConfirmation: (id, token, signal) => http.request(`/bookings/${encoded(id)}/confirmation`, { signal, retry: false, headers: { Authorization: `Bearer ${token}` } }),
      mine: (params, signal) => http.request(`/customer/bookings${pageQuery(params)}`, { signal }),
      getMine: (id, signal) => http.request(`/customer/bookings/${encoded(id)}`, { signal }),
      cancelMine: (id, signal) => http.request(`/customer/bookings/${encoded(id)}/cancel`, { method: "POST", signal, retry: false }),
    },
    payments: { createIntent: (body, key, signal) => http.request("/payments/intents", { method: "POST", body, signal, retry: false, headers: { "Idempotency-Key": key } }) },
    customer: {
      profile: (signal) => http.request("/customer/profile", { signal }),
      updateProfile: (body, signal) => http.request("/customer/profile", { method: "PATCH", body, signal, retry: false }),
      addresses: (signal) => http.request("/customer/addresses", { signal }),
      addAddress: (body, signal) => http.request("/customer/addresses", { method: "POST", body, signal, retry: false }),
      updateAddress: (id, body, signal) => http.request(`/customer/addresses/${encoded(id)}`, { method: "PATCH", body, signal, retry: false }),
      deleteAddress: (id, signal) => http.request(`/customer/addresses/${encoded(id)}`, { method: "DELETE", signal, retry: false }),
      payments: (params, signal) => http.request(`/customer/payments${pageQuery(params)}`, { signal }),
      payment: (id, signal) => http.request(`/customer/payments/${encoded(id)}`, { signal }),
    },
    quotes: {
      list: (params, signal) => http.request(`/customer/quotes${pageQuery(params)}`, { signal }),
      get: (id, signal) => http.request(`/customer/quotes/${encoded(id)}`, { signal }),
      decide: (id, approve, signal) => http.request(`/customer/quotes/${encoded(id)}/decision`, { method: "POST", body: { approve }, signal, retry: false }),
    },
  };
}
