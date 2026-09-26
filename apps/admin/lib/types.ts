// Admin-local mirrors of the canonical API schemas (apps/api/openapi.json).
// Shared packages are owned elsewhere; these types only cover admin screens.

export type Uuid = string;

export interface Page<T> { items: T[]; total: number; page: number; page_size: number }

// ----- users & access ------------------------------------------------------

export type UserRole = "customer" | "vendor_admin" | "technician" | "operations" | "finance" | "admin";
export type AccessRole =
  | "customer" | "vendor_admin" | "technician" | "operations" | "ops_manager" | "support" | "finance"
  | "quality" | "trust_safety" | "sales" | "marketing" | "admin" | "superadmin";
export type Department =
  | "customer" | "provider" | "field_service" | "dispatch" | "customer_support" | "vendor_success"
  | "finance" | "quality" | "trust_safety" | "sales" | "marketing" | "administration";
export type TenantScope = "global" | "brand" | "vendor";
export type AdminUserStatus = "active" | "disabled";

export interface AccessAssignment {
  role: AccessRole;
  department: Department;
  tenant_scope: TenantScope;
  vendor_id: Uuid | null;
  is_primary: boolean;
}

export interface PortalContext {
  user: { id: Uuid; email: string; full_name: string; role: UserRole; is_active: boolean; email_verified: boolean };
  brand_key: string;
  dashboard_path: string;
  roles: AccessRole[];
  departments: Department[];
  permissions: string[];
  assignments: AccessAssignment[];
  identity_mode: string;
}

export interface AdminUserSummary {
  id: Uuid;
  email: string;
  full_name: string;
  role: UserRole;
  status: AdminUserStatus;
  email_verified: boolean;
  identity_linked: boolean;
  created_at: string;
  updated_at: string;
}

export interface AdminUserDetail extends AdminUserSummary {
  identity_authority: "keycloak" | "local";
  identity_links: { issuer: string; linked_at: string; last_seen_at: string | null }[];
  active_session_count: number;
  access: PortalContext;
}

export interface PermissionOverride { permission: string; allow: boolean; source: "role" | "user"; role: AccessRole | null }

export interface EffectiveAccess {
  user_id: Uuid;
  brand_key: string;
  status: AdminUserStatus;
  identity_authority: "keycloak" | "local";
  managed_profile: boolean;
  access: PortalContext;
  overrides: PermissionOverride[];
  effective_permissions: string[];
}

export interface AccessCatalog { roles: AccessRole[]; departments: Department[]; tenant_scopes: TenantScope[] }

// ----- provider applications ----------------------------------------------

export type ProviderApplicationStatus = "DRAFT" | "PENDING" | "INFORMATION_REQUESTED" | "APPROVED" | "REJECTED";

export interface ProviderApplication {
  id: Uuid;
  vendor_id: Uuid;
  status: ProviderApplicationStatus;
  identity: Record<string, unknown>;
  business: Record<string, unknown>;
  contact_details: Record<string, unknown>;
  services: unknown[];
  skills: unknown[];
  service_areas: unknown[];
  postal_codes: unknown[];
  availability: Record<string, unknown>;
  capacity: Record<string, unknown>;
  licenses: unknown[];
  insurance: unknown[];
  compliance_documents: unknown[];
  version: number;
  submitted_at: string | null;
  decided_at: string | null;
  reviewed_by: Uuid | null;
  decision_reason: string | null;
  requested_information: string | null;
}

export interface ProviderApplicationList { items: ProviderApplication[]; total: number }

// ----- geography -----------------------------------------------------------

export interface ServiceZone {
  id: Uuid;
  legal_entity_id: Uuid;
  name: string;
  country_code: string | null;
  state_code: string | null;
  city: string | null;
  postal_codes: string[];
  service_ids: Uuid[];
  center: { latitude: number; longitude: number } | null;
  radius_miles: number | null;
  boundary_configured: boolean;
  priority: number;
  regular_service_enabled: boolean;
  emergency_enabled: boolean;
  active: boolean;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface PostalCode {
  id: Uuid;
  service_area_id: Uuid;
  postal_code: string;
  city: string | null;
  state_code: string | null;
  active: boolean;
  regular_service_enabled: boolean;
  emergency_service_enabled: boolean;
  priority: number;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface ServiceZoneCoverage { service_zone: ServiceZone; postal_codes: PostalCode[]; service_ids: Uuid[] }

export interface PostalCodeImportRow {
  postal_code: string;
  city?: string | null;
  state_code?: string | null;
  active?: boolean;
  regular_service_enabled?: boolean;
  emergency_service_enabled?: boolean;
  priority?: number;
}

export interface PostalCodeImportResult {
  id: Uuid;
  service_area_id: Uuid;
  idempotency_key: string;
  status: "PENDING" | "COMPLETED" | "FAILED";
  total_rows: number;
  imported_rows: number;
  rejected_rows: number;
  errors: Record<string, unknown>[];
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

// ----- finance -------------------------------------------------------------

export type CapabilityState = "ENABLED" | "DISABLED" | "NOT_IMPLEMENTED";
export interface FinanceStatus { payouts_enabled: boolean; payments_enabled: boolean; capabilities: Record<string, CapabilityState> }

export type PayoutStatus = "DRAFT" | "PENDING_APPROVAL" | "APPROVED" | "PROCESSING" | "PAID" | "FAILED" | "CANCELLED";
export type EarningStatus = "PENDING" | "AVAILABLE" | "HELD" | "APPROVED" | "BATCHED" | "PAID" | "CANCELLED" | "REVERSED";
export type PayoutAction = "approve" | "submit";

export interface PayoutBatchSummary {
  id: Uuid;
  reference: string;
  status: PayoutStatus;
  currency: string;
  total_minor: number;
  earning_count: number;
  reviewed_by: Uuid | null;
  reviewed_at: string | null;
  approved_by: Uuid | null;
  approved_at: string | null;
  submitted_at: string | null;
  provider_status: string | null;
  failure_reason: string | null;
  created_at: string;
}

export interface PayoutHistoryEntry {
  state: "CREATED" | "APPROVED" | "SUBMITTED" | "SUBMISSION_BLOCKED" | "CURRENT";
  status: PayoutStatus | null;
  occurred_at: string | null;
  actor_id?: Uuid | null;
  detail?: string | null;
}

export interface PayoutBatchDetail extends PayoutBatchSummary {
  provider_reference: string | null;
  earnings: { id: Uuid; vendor_id: Uuid; job_id: Uuid; net_minor: number; adjustment_total_minor: number; payable_minor: number; currency: string; status: EarningStatus }[];
  vendor_totals: { vendor_id: Uuid; earning_count: number; total_minor: number }[];
  history: PayoutHistoryEntry[];
  allowed_actions: PayoutAction[];
  payouts_enabled: boolean;
}

export interface PayoutCandidates { currency: string; vendor_id: Uuid | null; earning_count: number; total_minor: number; payouts_enabled: boolean }

export interface PendingPayoutTotal {
  currency: string;
  eligible_count: number;
  eligible_minor: number;
  pending_release_minor: number;
  held_minor: number;
  in_batch_minor: number;
  paid_minor: number;
}

export interface EarningsSummary {
  vendor_id: Uuid | null;
  by_status: { currency: string; status: EarningStatus; earning_count: number; payable_minor: number }[];
  pending_payouts: PendingPayoutTotal[];
  payouts_enabled: boolean;
}

export interface FinanceException {
  kind: "EARNING_HELD" | "EARNING_REVERSED" | "PAYOUT_FAILED" | "PAYOUT_SUBMISSION_BLOCKED" | "PAYOUT_PROCESSING_STALE";
  resource_type: "vendor_earning" | "payout_batch";
  resource_id: Uuid;
  status: string;
  currency: string;
  amount_minor: number;
  vendor_id: Uuid | null;
  reference: string | null;
  reason: string | null;
  occurred_at: string | null;
}

export interface PaymentRecord {
  id: Uuid;
  payment_purpose: string;
  booking_id: Uuid | null;
  quote_id: Uuid | null;
  lead_purchase_id: Uuid | null;
  provider: string;
  provider_payment_id: string | null;
  status: string;
  amount_minor: number;
  captured_amount_minor: number;
  currency: string;
  failure_code: string | null;
  created_at: string;
  updated_at: string;
}

export interface RefundRecord {
  id: Uuid;
  payment_id: Uuid;
  amount_minor: number;
  status: string;
  provider_refund_id: string | null;
  reason: string | null;
  created_by: Uuid;
  created_at: string;
}
