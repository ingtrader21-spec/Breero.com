import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type {
  AssignmentCandidates,
  CapacityBoard,
  IntegrationFailurePage,
  JobControlDetail,
  OperationsDashboard,
  QueueItem,
  ServiceAreaProjection,
} from "../../lib/types";
import { CapacityView } from "./CapacityView";
import { DashboardView } from "./DashboardView";
import { DispatchPanel } from "./DispatchPanel";
import { IntegrationFailuresView } from "./IntegrationFailuresView";
import { JobDetailView, WorkRequestList } from "./JobDetailView";
import { JobTable } from "./JobTable";
import { ServiceAreasView } from "./ServiceAreasView";
import { TransitionPanel } from "./TransitionPanel";

const NOW = "2026-09-25T12:00:00Z";
const noop = () => undefined;

function queueItem(overrides: Partial<QueueItem> = {}): QueueItem {
  return {
    job_id: "11111111-2222-4333-8444-555555555555",
    booking_id: "b0000000-0000-4000-8000-000000000000",
    status: "CREATED",
    version: 1,
    scheduled_start: "2026-09-25T13:00:00Z",
    scheduled_end: "2026-09-25T15:00:00Z",
    service_id: "s0000000-0000-4000-8000-000000000000",
    service_name: "Water heater repair",
    location: { city: "Austin", state_code: "TX", postal_code: "78701", country_code: "US", timezone_name: "America/Chicago", service_area_id: null, service_area_name: "Central Austin" },
    vendor: null,
    worker: null,
    live_offer_count: 0,
    unreviewed_work_request_count: 0,
    last_changed_at: NOW,
    risks: [{ code: "UNASSIGNED_NEAR_START", severity: "HIGH", detail: "Inside lead time" }],
    highest_severity: "HIGH",
    ...overrides,
  };
}

function jobDetail(overrides: Partial<JobControlDetail> = {}): JobControlDetail {
  return {
    generated_at: NOW,
    job: queueItem({ status: "ASSIGNED", version: 4, worker: { id: "w1", name: "Ana Diaz", status: "ACTIVE", available: true }, vendor: { id: "v1", name: "Acme", status: "ACTIVE" }, risks: [], highest_severity: null }),
    created_at: NOW,
    updated_at: NOW,
    booking: null,
    diagnostics: { diagnostic_notes: null, completion_notes: null, completed_at: null },
    assignments: [],
    offers: [],
    timeline: [
      { kind: "status", at: NOW, actor_id: null, actor_type: "operations", action: "reassigned", from_status: "ASSIGNED", to_status: "ASSIGNED", reason: "Rebalance", metadata: {} },
    ],
    work_requests: [
      { id: "wr-open", job_id: "j", status: "SUBMITTED", description: "Replace valve", line_items: [{}], subtotal_minor: 5000, tax_minor: 0, total_minor: 5000, currency: "USD", created_at: NOW },
      { id: "wr-done", job_id: "j", status: "DECLINED", description: "Old quote", line_items: [], subtotal_minor: 100, tax_minor: 0, total_minor: 100, currency: "USD", created_at: NOW },
    ],
    integration_events: [],
    actions: { allowed_transitions: ["EN_ROUTE", "CANCELLED"], technician_commands: ["en-route"], can_match: false, can_assign: false, can_reassign: true, reviewable_work_request_ids: ["wr-open"] },
    ...overrides,
  };
}

describe("dashboard", () => {
  it("renders server counts and links into filtered queues", () => {
    const data: OperationsDashboard = {
      generated_at: NOW,
      jobs_by_status: [{ status: "CREATED", count: 3 }, { status: "ASSIGNED", count: 2 }],
      active_jobs: 5,
      unassigned_jobs: 3,
      scheduled_next_24h: 4,
      live_offers: 1,
      work_requests_awaiting_review: 2,
      work_requests_awaiting_customer: 0,
      risk_by_severity: [{ severity: "CRITICAL", count: 1 }, { severity: "HIGH", count: 2 }, { severity: "MEDIUM", count: 0 }],
      at_risk_jobs: 3,
      risk_scan_truncated: true,
      workforce: { active_vendors: 2, active_workers: 6, dispatchable_workers: 4 },
      integrations: { failed: 1, retrying: 2 },
    };
    const html = renderToStaticMarkup(<DashboardView data={data} />);
    expect(html).toContain("1 critical");
    expect(html).toContain('href="/queue?status=CREATED"');
    expect(html).toContain("2 retrying");
    expect(html).toContain("scan limit was reached");
    expect(html).toContain("ops-stat--alert");
  });
});

describe("job table", () => {
  it("links jobs and shows server risk findings with area-level location only", () => {
    const html = renderToStaticMarkup(<JobTable items={[queueItem()]} generatedAt={NOW} emptyMessage="none" />);
    expect(html).toContain('href="/jobs/11111111-2222-4333-8444-555555555555"');
    expect(html).toContain("Unassigned near start");
    expect(html).toContain("Central Austin");
    expect(html).toContain("in 1h");
  });

  it("shows the empty state", () => {
    expect(renderToStaticMarkup(<JobTable items={[]} generatedAt={NOW} emptyMessage="No jobs match." />)).toContain("No jobs match.");
  });
});

describe("job detail", () => {
  it("renders timeline, diagnostics and only reviewable work-request actions", () => {
    const detail = jobDetail();
    const html = renderToStaticMarkup(
      <>
        <JobDetailView detail={detail} />
        <WorkRequestList detail={detail} busy={false} onReview={noop} />
      </>,
    );
    expect(html).toContain("Reassigned");
    expect(html).toContain("Rebalance");
    expect(html).toContain("Not recorded");
    expect(html).toContain("$50.00");
    expect(html.match(/Send to customer/g)).toHaveLength(1);
    expect(html).not.toContain("1 Private Street");
  });
});

describe("transition panel", () => {
  it("offers exactly the server-permitted transitions", () => {
    const html = renderToStaticMarkup(<TransitionPanel allowed={["EN_ROUTE", "CANCELLED"]} technicianCommands={["en-route"]} busy={false} onTransition={noop} />);
    const options = [...html.matchAll(/<option value="([A-Z_]+)"/g)].map((match) => match[1]);
    expect(options).toEqual(["EN_ROUTE", "CANCELLED"]);
    expect(html).toContain("Start travel (en route)");
    expect(html).toMatch(/<button type="submit"[^>]*disabled/);
  });

  it("explains terminal jobs instead of rendering controls", () => {
    const html = renderToStaticMarkup(<TransitionPanel allowed={[]} technicianCommands={[]} busy={false} onTransition={noop} />);
    expect(html).toContain("terminal state");
    expect(html).not.toContain("<select");
  });
});

describe("dispatch panel", () => {
  const candidates: AssignmentCandidates = {
    generated_at: NOW,
    job_id: "j",
    job_status: "ASSIGNED",
    job_version: 4,
    mode: "reassign",
    reserved_worker_id: "w1",
    candidates: [
      { worker_id: "w2", worker_name: "Ben Ortiz", vendor_id: "v1", vendor_name: "Acme", available: true, holds_reserved_slot: false, covers_job_postal_code: true, active_jobs: 1, currently_assigned: false, eligible: true, blocking_reasons: [] },
      { worker_id: "w1", worker_name: "Ana Diaz", vendor_id: "v1", vendor_name: "Acme", available: true, holds_reserved_slot: true, covers_job_postal_code: true, active_jobs: 2, currently_assigned: true, eligible: false, blocking_reasons: ["CURRENTLY_ASSIGNED"] },
    ],
  };

  it("disables ineligible candidates and explains why", () => {
    const html = renderToStaticMarkup(
      <DispatchPanel actions={jobDetail().actions} candidates={candidates} busy={false} onMatch={noop} onAssign={noop} onReassign={noop} />,
    );
    expect(html).toContain("Reassign job");
    expect(html).toContain("Already assigned to this job");
    expect(html).toMatch(/aria-label="Select Ana Diaz"[^>]*disabled|disabled[^>]*aria-label="Select Ana Diaz"/);
    expect(html).not.toMatch(/aria-label="Select Ben Ortiz"[^>]*disabled=""/);
    expect(html).not.toContain("Run matching");
  });

  it("hides dispatch controls when the server permits no dispatch change", () => {
    const actions = { ...jobDetail().actions, can_reassign: false };
    const html = renderToStaticMarkup(<DispatchPanel actions={actions} candidates={undefined} busy={false} onMatch={noop} onAssign={noop} onReassign={noop} />);
    expect(html).toContain("not permitted");
    expect(html).not.toContain("<form");
  });
});

describe("capacity, service areas and integrations", () => {
  it("flags over-capacity workers from server fields", () => {
    const board: CapacityBoard = {
      generated_at: NOW, date: "2026-09-25", weekday: 4, window_start: "2026-09-25T00:00:00Z", window_end: "2026-09-26T00:00:00Z",
      workers: [{ worker_id: "w1", worker_name: "Ana Diaz", worker_status: "ACTIVE", available: true, vendor_id: "v1", vendor_name: "Acme", vendor_status: "ACTIVE", shift_start: "08:00", shift_end: "17:00", daily_capacity: 2, jobs_in_window: 3, active_jobs: 3, covered_postal_codes: 4, covered_services: 2, utilization_percent: 150, over_capacity: true }],
      totals: { workers: 1, daily_capacity: 2, jobs_in_window: 3, workers_without_hours: 0, workers_over_capacity: 1 },
      truncated: false,
    };
    const html = renderToStaticMarkup(<CapacityView data={board} />);
    expect(html).toContain("Friday working hours");
    expect(html).toContain("150%");
    expect(html).toContain('style="width:100%"');
    expect(html).toContain("Over capacity");
  });

  it("shows the privacy statement and zone aggregates", () => {
    const data: ServiceAreaProjection = {
      generated_at: NOW,
      privacy: "Aggregate counts per BREERO service zone only.",
      unzoned_active_jobs: 2,
      areas: [{ service_area_id: "a1", name: "Central Austin", country_code: "US", state_code: "TX", city: "Austin", active: true, emergency_enabled: false, postal_code_count: 12, active_jobs: 3, unassigned_jobs: 1, covering_dispatchable_workers: 0 }],
    };
    const html = renderToStaticMarkup(<ServiceAreasView data={data} />);
    expect(html).toContain("Aggregate counts per BREERO service zone only.");
    expect(html).toContain("2 active job(s)");
    expect(html).toContain('href="/queue?service_area_id=a1"');
    expect(html).toContain("Jobs without dispatchable workers");
  });

  it("never offers an in-console retry and explains who may retry", () => {
    const base: IntegrationFailurePage = {
      generated_at: NOW,
      retry_permitted: false,
      items: [{ id: "e1", aggregate_type: "job", aggregate_id: "11111111-2222-4333-8444-555555555555", event_type: "job.completed", status: "FAILED_TERMINAL", attempt_count: 5, last_error_code: "ODOO_DOWN", last_error_at: NOW, next_attempt_at: NOW, created_at: NOW }],
    };
    const operations = renderToStaticMarkup(<IntegrationFailuresView data={base} />);
    expect(operations).toContain("requires a finance or admin account");
    expect(operations).toContain("ODOO_DOWN");
    expect(operations).toContain('href="/jobs/11111111-2222-4333-8444-555555555555"');
    expect(operations).not.toContain("<button");
    const admin = renderToStaticMarkup(<IntegrationFailuresView data={{ ...base, retry_permitted: true }} />);
    expect(admin).toContain("Admin portal");
  });
});
