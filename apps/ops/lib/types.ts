// App-local mirrors of the Operations Control Center API contract
// (apps/api/app/domains/dispatch/operations_schemas.py). Replace with
// @breero/api-client types once shared coverage for these routes exists.

export const JOB_STATUSES = [
  "CREATED",
  "MATCHING",
  "OFFERED",
  "ASSIGNED",
  "EN_ROUTE",
  "ON_SITE",
  "DIAGNOSING",
  "AWAITING_APPROVAL",
  "IN_PROGRESS",
  "COMPLETED",
  "CANCELLED",
] as const;
export type JobStatus = (typeof JOB_STATUSES)[number];

export const RISK_SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM"] as const;
export type RiskSeverity = (typeof RISK_SEVERITIES)[number];

export type RiskCode =
  | "UNASSIGNED_START_PASSED"
  | "UNASSIGNED_NEAR_START"
  | "NO_LIVE_OFFERS"
  | "ASSIGNED_START_PASSED"
  | "VISIT_OVERRUN"
  | "APPROVAL_STALLED"
  | "WORK_REQUEST_REVIEW_OVERDUE"
  | "ASSIGNED_WORKER_UNDISPATCHABLE";

export type WorkRequestStatus =
  | "DRAFT"
  | "SUBMITTED"
  | "PENDING_CUSTOMER"
  | "APPROVED_PENDING_PAYMENT"
  | "APPROVED"
  | "DECLINED"
  | "PAID"
  | "CANCELLED"
  | "EXPIRED";

export interface Risk { code: RiskCode; severity: RiskSeverity; detail: string }

export interface RiskPolicy {
  unassigned_lead_time_minutes: number;
  approval_stall_after_minutes: number;
  work_request_review_after_minutes: number;
}

export interface JobLocationSummary {
  city: string | null;
  state_code: string | null;
  postal_code: string | null;
  country_code: string | null;
  timezone_name: string | null;
  service_area_id: string | null;
  service_area_name: string | null;
}

export interface PartySummary { id: string; name: string; status: string; available?: boolean | null }

export interface QueueItem {
  job_id: string;
  booking_id: string;
  status: JobStatus;
  version: number;
  scheduled_start: string;
  scheduled_end: string;
  service_id: string;
  service_name: string | null;
  location: JobLocationSummary;
  vendor: PartySummary | null;
  worker: PartySummary | null;
  live_offer_count: number;
  unreviewed_work_request_count: number;
  last_changed_at: string;
  risks: Risk[];
  highest_severity: RiskSeverity | null;
}

export interface QueuePage {
  generated_at: string;
  items: QueueItem[];
  total: number;
  limit: number;
  offset: number;
  scan_truncated: boolean;
}

export interface SeverityCount { severity: RiskSeverity; count: number }
export interface RiskCodeCount { code: RiskCode; count: number }
export interface StatusCount { status: JobStatus; count: number }

export interface ExceptionQueue {
  generated_at: string;
  policy: RiskPolicy;
  items: QueueItem[];
  by_severity: SeverityCount[];
  by_code: RiskCodeCount[];
  scanned_jobs: number;
  scan_truncated: boolean;
}

export interface OperationsDashboard {
  generated_at: string;
  jobs_by_status: StatusCount[];
  active_jobs: number;
  unassigned_jobs: number;
  scheduled_next_24h: number;
  live_offers: number;
  work_requests_awaiting_review: number;
  work_requests_awaiting_customer: number;
  risk_by_severity: SeverityCount[];
  at_risk_jobs: number;
  risk_scan_truncated: boolean;
  workforce: { active_vendors: number; active_workers: number; dispatchable_workers: number };
  integrations: { failed: number; retrying: number };
}

export interface WorkerCapacity {
  worker_id: string;
  worker_name: string;
  worker_status: string;
  available: boolean;
  vendor_id: string;
  vendor_name: string;
  vendor_status: string;
  shift_start: string | null;
  shift_end: string | null;
  daily_capacity: number;
  jobs_in_window: number;
  active_jobs: number;
  covered_postal_codes: number;
  covered_services: number;
  utilization_percent: number | null;
  over_capacity: boolean;
}

export interface CapacityBoard {
  generated_at: string;
  date: string;
  weekday: number;
  window_start: string;
  window_end: string;
  workers: WorkerCapacity[];
  totals: {
    workers: number;
    daily_capacity: number;
    jobs_in_window: number;
    workers_without_hours: number;
    workers_over_capacity: number;
  };
  truncated: boolean;
}

export interface ServiceAreaOperations {
  service_area_id: string | null;
  name: string;
  country_code: string | null;
  state_code: string | null;
  city: string | null;
  active: boolean;
  emergency_enabled: boolean;
  postal_code_count: number;
  active_jobs: number;
  unassigned_jobs: number;
  covering_dispatchable_workers: number;
}

export interface ServiceAreaProjection {
  generated_at: string;
  areas: ServiceAreaOperations[];
  unzoned_active_jobs: number;
  privacy: string;
}

export interface IntegrationEventSummary {
  id: string;
  aggregate_type: string;
  aggregate_id: string;
  event_type: string;
  status: string;
  attempt_count: number;
  last_error_code: string | null;
  last_error_at: string | null;
  next_attempt_at: string;
  created_at: string;
}

export interface IntegrationFailurePage {
  generated_at: string;
  items: IntegrationEventSummary[];
  retry_permitted: boolean;
}

export interface AssignmentHistory {
  id: string;
  offer_id: string | null;
  vendor_id: string;
  worker_id: string;
  status: "ACTIVE" | "RELEASED" | "COMPLETED";
  assigned_by: string | null;
  assigned_at: string;
  released_at: string | null;
}

export interface OfferHistory {
  id: string;
  vendor_id: string;
  worker_id: string | null;
  status: "PENDING" | "ACCEPTED" | "DECLINED" | "EXPIRED" | "WITHDRAWN";
  round: number;
  score: number;
  expires_at: string;
  responded_at: string | null;
  created_at: string;
}

export interface TimelineEntry {
  kind: "status" | "audit" | string;
  at: string;
  actor_id: string | null;
  actor_type: string | null;
  action: string;
  from_status?: JobStatus | null;
  to_status?: JobStatus | null;
  reason?: string | null;
  metadata: Record<string, unknown>;
}

export interface WorkRequest {
  id: string;
  job_id: string;
  status: WorkRequestStatus;
  description: string;
  line_items: { description?: string; quantity?: number; unit_price_minor?: number }[];
  subtotal_minor: number;
  tax_minor: number;
  total_minor: number;
  currency: string;
  created_at: string;
}

export interface JobActions {
  allowed_transitions: JobStatus[];
  technician_commands: string[];
  can_match: boolean;
  can_assign: boolean;
  can_reassign: boolean;
  reviewable_work_request_ids: string[];
}

export interface JobControlDetail {
  generated_at: string;
  job: QueueItem;
  created_at: string;
  updated_at: string;
  booking: {
    id: string;
    reference: string;
    status: string;
    provider_worker_id: string | null;
    window_start: string;
    window_end: string;
  } | null;
  diagnostics: { diagnostic_notes: string | null; completion_notes: string | null; completed_at: string | null };
  assignments: AssignmentHistory[];
  offers: OfferHistory[];
  timeline: TimelineEntry[];
  work_requests: WorkRequest[];
  integration_events: IntegrationEventSummary[];
  actions: JobActions;
}

export type CandidateBlockingReason =
  | "JOB_NOT_ASSIGNABLE"
  | "WORKER_UNAVAILABLE"
  | "RESERVED_FOR_ANOTHER_WORKER"
  | "CURRENTLY_ASSIGNED";

export interface AssignmentCandidate {
  worker_id: string;
  worker_name: string;
  vendor_id: string;
  vendor_name: string;
  available: boolean;
  holds_reserved_slot: boolean;
  covers_job_postal_code: boolean;
  active_jobs: number;
  currently_assigned: boolean;
  eligible: boolean;
  blocking_reasons: CandidateBlockingReason[];
}

export interface AssignmentCandidates {
  generated_at: string;
  job_id: string;
  job_status: JobStatus;
  job_version: number;
  mode: "assign" | "reassign" | "none";
  reserved_worker_id: string | null;
  candidates: AssignmentCandidate[];
}

export interface OfferRead { id: string; job_id: string; vendor_id: string; worker_id: string | null; status: string; score: number; expires_at: string }
export interface AssignmentRead { id: string; job_id: string; vendor_id: string; worker_id: string; status: string; assigned_at: string }
export interface ReassignmentRead { assignment: AssignmentRead; released_assignment_id: string; job_id: string; job_status: JobStatus; job_version: number }
export interface JobRead { id: string; status: JobStatus; vendor_id: string | null; worker_id: string | null }

export interface OpsUser { id: string; email: string; full_name: string; role: string }
export interface OpsSession { access_token: string; user: OpsUser }
