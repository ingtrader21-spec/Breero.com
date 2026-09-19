export type UUID = string;
export type ISODate = string;
export type ISODateTime = string;
export type MoneyAmount = string;

export interface PublicCapabilities {
  request_intake: boolean;
  instant_booking: boolean;
  online_payments: boolean;
  automatic_assignment: boolean;
  provider_self_service: boolean;
  marketplace_matching: boolean;
  messaging: boolean;
  reviews: boolean;
}

export type QuestionType =
  | "text" | "textarea" | "number" | "boolean"
  | "single_choice" | "multi_choice";

export interface QuestionOption { value: string; label: string; description?: string }
export interface ServiceQuestion {
  id: UUID; key: string; label: string; help_text: string | null;
  question_type: QuestionType; required: boolean;
  options: QuestionOption[] | null; validation: Record<string, unknown> | null; sort_order: number;
}
export interface ServiceSummary {
  id: UUID; slug: string; name: string; description: string | null;
  base_price: MoneyAmount | null; duration_minutes: number | null;
  pricing_model?: string; is_active?: boolean; is_bookable?: boolean;
}
export interface ServiceDetail extends ServiceSummary { questions: ServiceQuestion[] }

export interface AddressValidationRequest {
  address: string; line1?: string; city?: string; postal_code?: string;
  country_code?: string; latitude?: number; longitude?: number;
}
export interface AddressValidation {
  serviceable: boolean; formatted_address: string; address_id: UUID | null;
  service_area_id: UUID | null; legal_entity_code: string | null;
}
export interface AvailabilitySearchRequest {
  service_id: UUID; address_id: UUID; date_from: ISODate; date_to: ISODate;
}
export interface AvailabilitySlot { start: ISODateTime; end: ISODateTime; remaining_capacity: number }

export interface CustomerInput { first_name: string; last_name: string; email: string; phone: string }
export interface BookingAnswerInput { question_id: UUID; value: string }
export interface BookingCreateRequest {
  service_id: UUID; customer: CustomerInput; address_id: UUID;
  window: { start: ISODateTime; end: ISODateTime }; answers: BookingAnswerInput[];
}
export interface Booking {
  id: UUID; reference: string; status: string; total_amount: MoneyAmount; currency: string;
  window_start: ISODateTime; window_end: ISODateTime; payment_required: boolean;
}
export interface BookingCreateResponse extends Booking { guest_confirmation_token: string | null }
export interface BookingConfirmation {
  booking_id: UUID; reference: string; booking_status: string; payment_status: string;
  window_start: ISODateTime; window_end: ISODateTime; amount_minor: number; currency: string;
  next_action: "confirmed" | "retry_payment" | "booking_unavailable" | "await_payment_confirmation";
}
export interface CustomerBookingList { items: Booking[] }

export type UserRole = "customer" | "vendor_admin" | "technician" | "operations" | "finance" | "admin";
export interface User { id: UUID; email: string; full_name: string; role: UserRole; is_active: boolean; email_verified?: boolean }
export interface LoginRequest { email: string; password: string }
export interface RegisterRequest extends LoginRequest { full_name: string }
export interface AuthSession { access_token: string; token_type: "bearer"; expires_in: number; refresh_token?: string; refresh_expires_in?: number; user: User }
export interface RefreshRequest { refresh_token: string }
export interface MessageResponse { message: string }
export interface ForgotPasswordRequest { email: string }
export interface ResetPasswordRequest { token: string; new_password: string }
export interface ChangePasswordRequest { current_password: string; new_password: string }
export interface TokenRequest { token: string }

export type PaymentStatus = "created" | "requires_action" | "authorized" | "captured" | "failed" | "canceled" | "refunded" | "partially_refunded";
export interface PaymentIntentRequest {
  booking_id?: UUID; quote_id?: UUID; payment_purpose?: "BOOKING_DIAGNOSTIC" | "QUOTE_ADDITIONAL_WORK";
  amount_minor: number; currency?: string; capture_method?: "automatic" | "manual"; metadata?: Record<string, string>;
}
export interface Payment {
  id: UUID; booking_id: UUID | null; quote_id?: UUID | null; payment_purpose?: "BOOKING_DIAGNOSTIC" | "QUOTE_ADDITIONAL_WORK"; provider: string; status: PaymentStatus;
  amount_minor: number; currency: string; captured_amount_minor: number;
  client_secret: string | null; failure_code: string | null;
  created_at: ISODateTime; updated_at: ISODateTime;
}

export interface QuoteLine { description: string; quantity: number; unit_price_minor: number }
export interface Quote { id: UUID; job_id: UUID; status: string; description: string; line_items: QuoteLine[]; subtotal_minor: number; tax_minor: number; total_minor: number; currency: string; created_at: ISODateTime }
export interface CustomerProfile { id: UUID; email: string; full_name: string; phone: string; email_verified: boolean }
export interface CustomerProfilePatch { full_name?: string; phone?: string }
export interface CustomerAddress { id: UUID; line1: string; city: string; postal_code: string; country_code: string }
export interface CustomerAddressInput { line1: string; city: string; postal_code: string; country_code: string; latitude: number; longitude: number }
export interface Page<T> { items: T[]; total: number; page: number; page_size: number }
export interface CustomerPayment {
  id: UUID; booking_id: UUID | null; quote_id: UUID | null;
  payment_purpose: "BOOKING_DIAGNOSTIC" | "QUOTE_ADDITIONAL_WORK";
  provider: string; status: PaymentStatus; amount_minor: number;
  captured_amount_minor: number; refunded_amount_minor: number; currency: string;
  failure_code: string | null; created_at: ISODateTime; updated_at: ISODateTime;
}

export * from "./portal";
