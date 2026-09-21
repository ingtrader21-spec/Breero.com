export type PortalKind = "partner" | "ops" | "admin";
export type PortalHttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export interface PortalApiRule {
  prefix: string;
  methods: readonly PortalHttpMethod[];
}

export interface PortalRuntimeConfig {
  kind: PortalKind;
  title: string;
  eyebrow: string;
  allowedRoles: readonly string[];
  apiRules: readonly PortalApiRule[];
  homePath?: string;
}

export interface PortalUser {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  email_verified: boolean;
}

export interface PortalAssignment {
  role: string;
  department: string;
  tenant_scope: string;
  vendor_id: string | null;
  is_primary: boolean;
}

export interface PortalContext {
  user: PortalUser;
  brand_key: string;
  dashboard_path: string;
  roles: string[];
  departments: string[];
  permissions: string[];
  assignments: PortalAssignment[];
  identity_mode: "keycloak" | "local";
}

export interface PortalCapabilities {
  request_intake: boolean;
  scheduling: boolean;
  instant_booking: boolean;
  online_payments: boolean;
  payouts: boolean;
  automatic_assignment: boolean;
  provider_self_service: boolean;
  marketplace_matching: boolean;
  messaging: boolean;
  reviews: boolean;
  middleware_delivery: boolean;
  transactional_email_mode: string;
  transactional_sms_mode: string;
}

export interface PortalSessionView {
  user: PortalUser;
  context: PortalContext;
  capabilities: PortalCapabilities;
  csrf_token: string;
  expires_at: number;
}

export interface PortalProblem {
  status: number;
  message: string;
  requestId?: string;
  code?: string;
}

export type PortalSessionState =
  | { status: "loading" }
  | { status: "anonymous"; message?: string }
  | { status: "authenticated"; session: PortalSessionView };
