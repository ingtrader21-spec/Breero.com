// Partner-local mirrors of the provider API response contracts (apps/api/openapi.json).
// Shared generated types belong to @breero/types; these stay local until that package
// publishes provider self-service contracts.

export type ApplicationStatus = "DRAFT" | "PENDING" | "INFORMATION_REQUESTED" | "APPROVED" | "REJECTED";
export type VendorStatus = "PENDING" | "ACTIVE" | "SUSPENDED" | "REJECTED";
export type ApprovalStatus = "PENDING" | "APPROVED" | "REJECTED";
export type WorkerStatus = "INVITED" | "ACTIVE" | "INACTIVE";
export type QualificationType = "LICENSE" | "INSURANCE" | "CERTIFICATION" | "BACKGROUND_CHECK" | "TRAINING" | "OTHER";
export type QualificationStatus = "DRAFT" | "SUBMITTED" | "WITHDRAWN";
export type QualificationReviewStatus = "NOT_SUBMITTED" | "PENDING_REVIEW" | "APPROVED" | "REJECTED" | "INFORMATION_REQUESTED";
export type OfferStatus = "PENDING" | "ACCEPTED" | "DECLINED" | "EXPIRED" | "WITHDRAWN";
export type JobStatus =
  | "CREATED" | "MATCHING" | "OFFERED" | "ASSIGNED" | "EN_ROUTE" | "ON_SITE" | "DIAGNOSING"
  | "AWAITING_APPROVAL" | "IN_PROGRESS" | "COMPLETED" | "CANCELLED";

export interface SessionUser { email: string; full_name: string; role: string }
export interface Session { access_token: string; user: SessionUser }

export interface ProviderProfile {
  id: string;
  legal_name: string;
  display_name: string;
  email: string;
  phone: string;
  status: VendorStatus;
  service_radius_meters: number;
}
export type ProviderProfilePatch = Partial<Pick<ProviderProfile, "legal_name" | "display_name" | "phone" | "service_radius_meters">>;

export type JsonObject = Record<string, unknown>;

export interface ProviderApplication {
  id: string;
  status: ApplicationStatus;
  identity: JsonObject;
  business: JsonObject;
  contact_details: JsonObject;
  services: unknown[];
  skills: unknown[];
  service_areas: JsonObject[];
  postal_codes: string[];
  availability: JsonObject;
  capacity: JsonObject;
  licenses: JsonObject[];
  insurance: JsonObject[];
  compliance_documents: string[];
  version: number;
  submitted_at: string | null;
  decided_at: string | null;
  decision_reason: string | null;
  requested_information: string | null;
}

export interface OnboardingPatch {
  identity?: JsonObject;
  business?: JsonObject;
  contact_details?: JsonObject;
  service_areas?: JsonObject[];
  postal_codes?: string[];
  capacity?: JsonObject;
}

export interface OnboardingChecklist {
  application_id: string;
  status: ApplicationStatus;
  version: number;
  editable: boolean;
  submittable: boolean;
  missing: string[];
  requested_information: string | null;
  decision_reason: string | null;
  submitted_at: string | null;
  decided_at: string | null;
}

export interface CatalogService { id: string; slug: string; name: string; category: string; is_active: boolean }
export interface CatalogSkill { id: string; key: string; name: string; category: string; description: string | null; provider_approval_required: boolean }

export interface ProviderService {
  id: string;
  service_id: string;
  service_name: string;
  service_category: string;
  status: ApprovalStatus;
  active: boolean;
  display_order: number;
  required_skills: (CatalogSkill & { required: boolean })[];
  version: number;
}

export interface ProviderSkill {
  id: string;
  worker_id: string;
  skill: CatalogSkill;
  status: ApprovalStatus;
  active: boolean;
  version: number;
}

export interface ProviderWorker {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  status: WorkerStatus;
  available: boolean;
  skills: string[];
  has_account: boolean;
  is_account_owner: boolean;
}
export interface ProviderWorkerInput { first_name: string; last_name: string; email: string; phone: string }

export interface AvailabilityRuleInput {
  worker_id?: string | null;
  weekday: number;
  start_time: string;
  end_time: string;
  timezone: string;
  valid_from?: string | null;
  valid_until?: string | null;
}
export interface AvailabilityRule extends Required<AvailabilityRuleInput> { id: string; version: number }

export interface BlackoutInput { worker_id?: string | null; starts_at: string; ends_at: string; timezone: string; reason?: string | null }
export interface BlackoutPeriod { id: string; worker_id: string | null; starts_at: string; ends_at: string; timezone: string; reason: string | null; version: number }

export interface AvailabilitySnapshot { rules: AvailabilityRule[]; blackouts: BlackoutPeriod[]; consumed_by_scheduling: boolean }
export interface AvailabilityPreview {
  window_start: string;
  window_end: string;
  intervals: { worker_id: string | null; starts_at: string; ends_at: string; timezone: string }[];
}

export interface QualificationInput {
  worker_id?: string | null;
  qualification_type: QualificationType;
  title: string;
  issuer?: string | null;
  jurisdiction?: string | null;
  reference_last4?: string | null;
  issued_on?: string | null;
  expires_on?: string | null;
  evidence_reference?: string | null;
}
export interface Qualification extends Required<QualificationInput> {
  id: string;
  status: QualificationStatus;
  review_status: QualificationReviewStatus;
  review_reason: string | null;
  reviewed_at: string | null;
  submitted_at: string | null;
  is_expired: boolean;
  version: number;
}
export interface QualificationList {
  items: Qualification[];
  total: number;
  evidence_storage: { upload_enabled: boolean; reason: string };
}

export interface ProviderJob {
  id: string;
  booking_id: string;
  service_id: string;
  service_name: string | null;
  status: JobStatus;
  scheduled_start: string;
  scheduled_end: string;
  worker_id: string | null;
  completed_at: string | null;
}

export interface ProfessionalLead {
  id: string;
  service_category: string;
  location_summary: string;
  price_minor: number;
  currency: string;
  status: string;
  expires_at: string | null;
  opportunity_disclosure: string;
}

export interface ProviderOffer {
  id: string;
  job_id: string;
  worker_id: string | null;
  status: OfferStatus;
  round: number;
  expires_at: string;
  responded_at: string | null;
  job_status: JobStatus | null;
  service_name: string | null;
  scheduled_start: string | null;
  scheduled_end: string | null;
}
