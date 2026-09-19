import type { UUID, User } from "./index";

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

export interface AccessProfileUpdate {
  brand_key?: string;
  assignments: AccessAssignmentInput[];
}

export interface AccessCatalog {
  roles: AccessRole[];
  departments: Department[];
  tenant_scopes: TenantScope[];
}

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

export interface LoginMode {
  mode: "keycloak" | "local";
  issuer: string;
}
