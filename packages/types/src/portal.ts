import type { ISODateTime, UUID, User } from "./index";

export type AccessRole =
  | "customer"
  | "vendor_admin"
  | "technician"
  | "operations"
  | "ops_manager"
  | "support"
  | "finance"
  | "quality"
  | "trust_safety"
  | "sales"
  | "marketing"
  | "admin"
  | "superadmin";

export type Department =
  | "customer"
  | "provider"
  | "field_service"
  | "dispatch"
  | "customer_support"
  | "vendor_success"
  | "finance"
  | "quality"
  | "trust_safety"
  | "sales"
  | "marketing"
  | "administration";

export type TenantScope = "global" | "brand" | "vendor";

export interface AccessAssignment {
  role: AccessRole;
  department: Department;
  tenant_scope: TenantScope;
  vendor_id: UUID | null;
  is_primary: boolean;
}
export interface AccessAssignmentInput {
  role: AccessRole;
  department: Department;
  tenant_scope: TenantScope;
  vendor_id?: UUID | null;
  is_primary?: boolean;
}
export interface AccessProfileUpdate { brand_key?: string; assignments: AccessAssignmentInput[] }
export interface AccessCatalog { roles: AccessRole[]; departments: Department[]; tenant_scopes: TenantScope[] }
export interface PortalContext {
  user: User;
  brand_key: string;
  dashboard_path: string;
  roles: AccessRole[];
  departments: Department[];
  permissions: string[];
  assignments: AccessAssignment[];
  identity_mode: "keycloak" | "local";
}
export interface LoginMode { mode: "keycloak" | "local"; issuer: string }

export interface EmailDomain {
  id: UUID; brand_key: string; vendor_id: UUID | null; domain: string;
  verification_status: string; dkim_selector: string | null; return_path_domain: string | null;
  active: boolean; created_at: ISODateTime;
}
export interface EmailDomainCreate { brand_key?: string; vendor_id?: UUID | null; domain: string; dkim_selector?: string | null; return_path_domain?: string | null }
export interface EmailSender {
  id: UUID; brand_key: string; vendor_id: UUID | null; domain_id: UUID; local_part: string;
  display_name: string; reply_to: string | null; active: boolean; created_at: ISODateTime;
}
export interface EmailSenderCreate { brand_key?: string; vendor_id?: UUID | null; domain_id: UUID; local_part: string; display_name: string; reply_to?: string | null }
export interface EmailCredential {
  id: UUID; brand_key: string; vendor_id: UUID | null; provider: string; label: string;
  username: string | null; smtp_host: string | null; smtp_port: number | null; use_tls: boolean;
  active: boolean; secret_configured: boolean; created_at: ISODateTime;
}
export interface EmailCredentialCreate {
  brand_key?: string; vendor_id?: UUID | null; provider: string; label: string; username?: string | null;
  secret_ref: string; smtp_host?: string | null; smtp_port?: number | null; use_tls?: boolean;
}
export interface EmailComposeRequest {
  brand_key?: string; vendor_id?: UUID | null; sender_id: UUID; credential_id: UUID;
  to_email: string; subject: string; text_body: string; idempotency_key: string;
}
export interface TenantEmailMessage {
  id: UUID; brand_key: string; vendor_id: UUID | null; sender_id: UUID; credential_id: UUID;
  to_email: string; subject: string; status: string; idempotency_key: string;
  queued_at: ISODateTime | null; delivered_at: ISODateTime | null; provider_message_id: string | null;
  created_at: ISODateTime;
}
export interface EmailOutboxEntry {
  id: UUID; message_id: UUID; status: string; attempts: number;
  next_attempt_at: ISODateTime; last_error_code: string | null;
}
