"use client";

import { type FormEvent, useMemo, useState } from "react";

import {
  DataTable,
  MetricCard,
  PortalApplication,
  PortalError,
  PortalLoading,
  PortalNotice,
  PortalSection,
  PortalSessionProvider,
  StatusBadge,
  type DataColumn,
  type PortalNavigationItem,
  usePortalQuery,
  usePortalSession,
} from "@breero/portal";

import { portalRuntime } from "../portal.config";

type StatusCount = { status: string; count: number };
type OperationsOverview = {
  intake_items_total: number;
  bookings: StatusCount[];
  jobs: StatusCount[];
  vendors: StatusCount[];
  provider_applications: StatusCount[];
  outbox: StatusCount[];
};
type DispatcherAudit = {
  action: string;
  actor_id: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
};
type DispatcherQueueItem = {
  request_id: string;
  submission_type: string;
  created_at: string;
  request_age_seconds: number;
  required_follow_up: boolean;
  customer_timezone: string | null;
  address_verification_state: string | null;
  manual_dispatch_state: string | null;
  provider_assigned: boolean;
  contact_attempts: Record<string, unknown>[];
  downstream_status: string;
  payload: Record<string, unknown>;
  audit_history: DispatcherAudit[];
};
type Offer = {
  id: string;
  job_id: string;
  vendor_id: string;
  worker_id: string | null;
  status: string;
};
type Assignment = {
  id: string;
  job_id: string;
  vendor_id: string;
  worker_id: string | null;
  status: string;
};

const navigation: PortalNavigationItem[] = [
  { id: "overview", label: "Overview", description: "Authoritative marketplace and delivery state." },
  { id: "queue", label: "Dispatch queue", description: "Review and update public service requests." },
  { id: "assignment", label: "Manual assignment", description: "Match and assign jobs with explicit operator intent." },
  { id: "booking", label: "Booking confirmation", description: "Confirm a booking only after worker selection and review." },
  { id: "security", label: "Security", description: "Effective identity, tenant, and authorization scope." },
];

function count(rows: StatusCount[]): number {
  return rows.reduce((total, row) => total + row.count, 0);
}

function secondsLabel(value: number): string {
  if (value < 60) return `${value}s`;
  if (value < 3600) return `${Math.floor(value / 60)}m`;
  return `${Math.floor(value / 3600)}h`;
}

export function OperationsWorkspacePage() {
  const [activeId, setActiveId] = useState("overview");
  return (
    <PortalSessionProvider>
      <PortalApplication
        config={portalRuntime}
        navigation={navigation}
        activeId={activeId}
        onNavigate={setActiveId}
      >
        <OperationsPanel activeId={activeId} />
      </PortalApplication>
    </PortalSessionProvider>
  );
}

function OperationsPanel({ activeId }: { activeId: string }) {
  const overview = usePortalQuery<OperationsOverview>("/portal/operations/overview");
  const queue = usePortalQuery<DispatcherQueueItem[]>("/operations/dispatcher/queue");
  const { state } = usePortalSession();
  if (state.status !== "authenticated") return null;
  if (activeId === "queue") return <DispatchQueuePanel query={queue} />;
  if (activeId === "assignment") return <ManualAssignmentPanel />;
  if (activeId === "booking") return <BookingConfirmationPanel />;
  if (activeId === "security") {
    return (
      <PortalSection title="Effective operations access" subtitle="Resolved by the backend for this session.">
        <dl className="portal-definition-grid">
          <div><dt>Identity mode</dt><dd>{state.session.context.identity_mode}</dd></div>
          <div><dt>Roles</dt><dd>{state.session.context.roles.join(", ") || "None"}</dd></div>
          <div><dt>Departments</dt><dd>{state.session.context.departments.join(", ") || "None"}</dd></div>
          <div><dt>Permissions</dt><dd>{state.session.context.permissions.length}</dd></div>
        </dl>
        <PortalNotice title="Manual-control release" tone="warning">
          Automatic provider assignment and automatic booking confirmation remain governed by the
          API capability flags. This workspace does not bypass them.
        </PortalNotice>
      </PortalSection>
    );
  }
  if (overview.loading) return <PortalLoading label="Loading operations overview" />;
  if (overview.error) return <PortalError error={overview.error} onRetry={overview.retry} />;
  if (!overview.data) return null;
  return (
    <div className="portal-stack">
      <section className="portal-metric-grid" aria-label="Operations totals">
        <MetricCard label="Intake" value={overview.data.intake_items_total} detail="Public submissions" />
        <MetricCard label="Bookings" value={count(overview.data.bookings)} detail="All lifecycle states" />
        <MetricCard label="Jobs" value={count(overview.data.jobs)} detail="All lifecycle states" />
        <MetricCard label="Providers" value={count(overview.data.vendors)} detail="All provider states" />
      </section>
      <PortalSection title="Operational state" subtitle="Counts are read directly from BREERO PostgreSQL.">
        <div className="portal-split">
          <StatusList title="Bookings" rows={overview.data.bookings} />
          <StatusList title="Jobs" rows={overview.data.jobs} />
          <StatusList title="Providers" rows={overview.data.vendors} />
          <StatusList title="Provider applications" rows={overview.data.provider_applications} />
          <StatusList title="Integration outbox" rows={overview.data.outbox} />
        </div>
      </PortalSection>
    </div>
  );
}

function StatusList({ title, rows }: { title: string; rows: StatusCount[] }) {
  return (
    <section className="portal-card">
      <h3>{title}</h3>
      {rows.length ? (
        <dl className="portal-definition-grid">
          {rows.map((row) => (
            <div key={`${title}-${row.status}`}>
              <dt><StatusBadge value={row.status} /></dt>
              <dd>{row.count}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p>No records are present.</p>
      )}
    </section>
  );
}

function DispatchQueuePanel({
  query,
}: {
  query: ReturnType<typeof usePortalQuery<DispatcherQueueItem[]>>;
}) {
  const { request } = usePortalSession();
  const [selected, setSelected] = useState<DispatcherQueueItem | null>(null);
  const [state, setState] = useState("PENDING_MANUAL_DISPATCH");
  const [outcome, setOutcome] = useState("");
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const columns = useMemo<DataColumn<DispatcherQueueItem>[]>(
    () => [
      { key: "type", label: "Type", render: (item) => <strong>{item.submission_type}</strong> },
      { key: "age", label: "Age", compact: true, render: (item) => secondsLabel(item.request_age_seconds) },
      { key: "dispatch", label: "Dispatch", render: (item) => <StatusBadge value={item.manual_dispatch_state ?? "unreviewed"} /> },
      { key: "delivery", label: "Delivery", render: (item) => <StatusBadge value={item.downstream_status} /> },
      { key: "follow", label: "Follow-up", compact: true, render: (item) => (item.required_follow_up ? "Required" : "No") },
      { key: "action", label: "Action", compact: true, render: (item) => <button type="button" className="portal-button" onClick={() => setSelected(item)}>Review</button> },
    ],
    [],
  );

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    setError("");
    try {
      await request<void>(`/operations/dispatcher/queue/${selected.request_id}`, {
        method: "PATCH",
        body: JSON.stringify({
          manual_dispatch_state: state,
          contact_outcome: outcome || null,
          note: note || null,
          required_follow_up: !["CLOSED", "CANCELLED"].includes(state),
        }),
      });
      setMessage(`Request ${selected.request_id} updated.`);
      setSelected(null);
      setNote("");
      setOutcome("");
      query.retry();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to update dispatch request");
    }
  }

  return (
    <div className="portal-stack">
      {message ? <PortalNotice title="Dispatch state updated" tone="success">{message}</PortalNotice> : null}
      {error ? <PortalNotice title="Dispatch update failed" tone="danger">{error}</PortalNotice> : null}
      <PortalSection title="Manual dispatch queue" subtitle="No automatic assignment or external send is performed here.">
        {query.loading ? <PortalLoading label="Loading dispatch queue" /> : null}
        {query.error ? <PortalError error={query.error} onRetry={query.retry} /> : null}
        {query.data ? <DataTable rows={query.data} columns={columns} rowKey={(item) => item.request_id} emptyTitle="The dispatch queue is empty" /> : null}
      </PortalSection>
      {selected ? (
        <PortalSection title={`Review ${selected.request_id}`} subtitle="The update is audited by the backend.">
          <form className="portal-form-grid" onSubmit={(event) => void submit(event)}>
            <label>Dispatch state
              <select value={state} onChange={(event) => setState(event.target.value)}>
                {[
                  "PENDING_MANUAL_DISPATCH", "CUSTOMER_CONTACT_PENDING", "CUSTOMER_CONTACTED",
                  "ADDRESS_VALIDATION_PENDING", "PROVIDER_MATCH_PENDING", "QUOTE_COORDINATION_PENDING",
                  "CANCELLED", "CLOSED",
                ].map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </label>
            <label>Contact outcome
              <select value={outcome} onChange={(event) => setOutcome(event.target.value)}>
                <option value="">No contact update</option>
                {["NO_ANSWER", "VOICEMAIL", "CUSTOMER_REACHED", "FOLLOW_UP_REQUESTED", "CANCELLED"].map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </label>
            <label className="portal-form-span">Operator note
              <textarea maxLength={1000} value={note} onChange={(event) => setNote(event.target.value)} />
            </label>
            <div className="portal-form-span portal-panel__actions">
              <button type="button" className="portal-button" onClick={() => setSelected(null)}>Cancel</button>
              <button type="submit" className="portal-button portal-button--primary">Save audited update</button>
            </div>
          </form>
        </PortalSection>
      ) : null}
    </div>
  );
}

function ManualAssignmentPanel() {
  const { request } = usePortalSession();
  const [jobId, setJobId] = useState("");
  const [vendorId, setVendorId] = useState("");
  const [workerId, setWorkerId] = useState("");
  const [reason, setReason] = useState("");
  const [offers, setOffers] = useState<Offer[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function match() {
    setError("");
    try {
      setOffers(await request<Offer[]>(`/operations/jobs/${jobId}/match`, { method: "POST" }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to match job");
    }
  }
  async function assign(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      const assignment = await request<Assignment>(`/operations/jobs/${jobId}/assign`, {
        method: "POST",
        body: JSON.stringify({ vendor_id: vendorId, worker_id: workerId || null, reason }),
      });
      setMessage(`Assignment ${assignment.id} created for job ${assignment.job_id}.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to assign job");
    }
  }
  return (
    <div className="portal-stack">
      {message ? <PortalNotice title="Manual assignment completed" tone="success">{message}</PortalNotice> : null}
      {error ? <PortalNotice title="Assignment operation failed" tone="danger">{error}</PortalNotice> : null}
      <PortalSection title="Match and assign a job" subtitle="Eligibility is evaluated before an explicit manual assignment.">
        <form className="portal-form-grid" onSubmit={(event) => void assign(event)}>
          <label>Job ID<input required value={jobId} onChange={(event) => setJobId(event.target.value)} /></label>
          <label>Vendor ID<input required value={vendorId} onChange={(event) => setVendorId(event.target.value)} /></label>
          <label>Worker ID (optional)<input value={workerId} onChange={(event) => setWorkerId(event.target.value)} /></label>
          <label className="portal-form-span">Reason<textarea required minLength={5} maxLength={1000} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
          <div className="portal-form-span portal-panel__actions">
            <button type="button" className="portal-button" disabled={!jobId} onClick={() => void match()}>Evaluate matching</button>
            <button type="submit" className="portal-button portal-button--primary">Assign manually</button>
          </div>
        </form>
      </PortalSection>
      {offers.length ? (
        <PortalSection title="Eligible offers" subtitle="Returned by the backend matching authority.">
          <DataTable
            rows={offers}
            columns={[
              { key: "vendor", label: "Vendor", render: (item) => item.vendor_id },
              { key: "worker", label: "Worker", render: (item) => item.worker_id ?? "Unassigned" },
              { key: "status", label: "Status", render: (item) => <StatusBadge value={item.status} /> },
            ]}
            rowKey={(item) => item.id}
          />
        </PortalSection>
      ) : null}
    </div>
  );
}

function BookingConfirmationPanel() {
  const { request } = usePortalSession();
  const [bookingId, setBookingId] = useState("");
  const [workerId, setWorkerId] = useState("");
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  async function confirm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      await request(`/operations/bookings/${bookingId}/confirm`, {
        method: "POST",
        body: JSON.stringify({ worker_id: workerId, reason }),
      });
      setMessage(`Booking ${bookingId} confirmed through the operator workflow.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to confirm booking");
    }
  }
  return (
    <PortalSection title="Operator booking confirmation" subtitle="This command requires a selected worker and a recorded reason.">
      {message ? <PortalNotice title="Booking confirmed" tone="success">{message}</PortalNotice> : null}
      {error ? <PortalNotice title="Confirmation failed" tone="danger">{error}</PortalNotice> : null}
      <form className="portal-form-grid" onSubmit={(event) => void confirm(event)}>
        <label>Booking ID<input required value={bookingId} onChange={(event) => setBookingId(event.target.value)} /></label>
        <label>Worker ID<input required value={workerId} onChange={(event) => setWorkerId(event.target.value)} /></label>
        <label className="portal-form-span">Reason<textarea required minLength={5} maxLength={1000} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
        <div className="portal-form-span"><button type="submit" className="portal-button portal-button--primary">Confirm booking</button></div>
      </form>
    </PortalSection>
  );
}
