"use client";

import {
  type ChangeEvent,
  type FormEvent,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  CapabilityGrid,
  DataTable,
  formatDate,
  formatLabel,
  formatMoney,
  MetricCard,
  PortalApplication,
  PortalConfirmForm,
  PortalEmpty,
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
type MoneyStatus = { status: string; currency: string; count: number; amount_minor: number };

type Vendor = {
  id: string;
  legal_name: string;
  display_name: string;
  email: string;
  phone: string;
  status: string;
  capabilities: unknown[];
  service_radius_meters: number;
};

type ProviderApplication = {
  id: string;
  vendor_id: string;
  status: string;
  identity: Record<string, unknown>;
  business: Record<string, unknown>;
  contact_details: Record<string, unknown>;
  services: string[];
  skills: string[];
  service_areas: Record<string, unknown>[];
  postal_codes: string[];
  availability: Record<string, unknown>;
  capacity: Record<string, unknown>;
  licenses: Record<string, unknown>[];
  insurance: Record<string, unknown>[];
  compliance_documents: string[];
  version: number;
  submitted_at: string | null;
  decided_at: string | null;
  decision_reason: string | null;
  requested_information: string | null;
};

type Job = {
  id: string;
  booking_id: string;
  customer_id: string | null;
  service_id: string;
  status: string;
  scheduled_start: string;
  scheduled_end: string;
  vendor_id: string | null;
  worker_id: string | null;
  diagnostic_notes: string | null;
  completion_notes: string | null;
};

type Worker = {
  id: string;
  vendor_id: string;
  user_id: string | null;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  status: string;
  skills: unknown[];
  available: boolean;
};

type Credential = {
  id: string;
  vendor_id: string;
  credential_type: string;
  jurisdiction: string;
  reference_last4: string | null;
  expires_on: string;
  verified: boolean;
};

type CatalogSkill = {
  id: string;
  key: string;
  name: string;
  category: string;
  description: string | null;
  provider_approval_required: boolean;
  required?: boolean;
};

type ProviderService = {
  id: string;
  vendor_id: string;
  service_id: string;
  service_slug: string;
  service_name: string;
  service_category: string;
  status: string;
  active: boolean;
  display_order: number;
  provider_approval_required: boolean;
  required_skills: CatalogSkill[];
  version: number;
  created_at: string;
  updated_at: string;
};

type ProviderSkill = {
  id: string;
  vendor_id: string;
  worker_id: string;
  skill: CatalogSkill;
  status: string;
  active: boolean;
  version: number;
  created_at: string;
  updated_at: string;
};

type Service = {
  id: string;
  slug: string;
  name: string;
  category: string;
  description?: string | null;
  is_active?: boolean;
};

type Earning = {
  id: string;
  vendor_id: string;
  job_id: string;
  gross_minor: number;
  fee_minor: number;
  net_minor: number;
  adjustment_total_minor: number;
  payable_minor: number;
  currency: string;
  status: string;
  available_at: string;
  payout_batch_id: string | null;
  created_at: string;
};

type PayoutBatch = {
  id: string;
  reference: string;
  status: string;
  currency: string;
  total_minor: number;
  earning_count: number;
  reviewed_at: string | null;
  approved_at: string | null;
  submitted_at: string | null;
  provider_status: string | null;
  failure_reason: string | null;
  created_at: string;
};

type ProviderOverview = {
  vendor: Vendor;
  application: ProviderApplication | null;
  capabilities: Parameters<typeof CapabilityGrid>[0]["capabilities"];
  workers_total: number;
  workers_available: number;
  services_active: number;
  skills_active: number;
  credentials_total: number;
  credentials_verified: number;
  credentials_expiring_soon: number;
  jobs: StatusCount[];
  earnings: MoneyStatus[];
  recent_jobs: Job[];
  recent_earnings: Earning[];
  recent_payout_batches: PayoutBatch[];
};

type ListResponse<T> = { items: T[]; total: number };

function sumCounts(rows: StatusCount[], match?: readonly string[]): number {
  if (!match) return rows.reduce((total, item) => total + item.count, 0);
  const accepted = new Set(match.map((value) => value.toUpperCase()));
  return rows.reduce(
    (total, item) => total + (accepted.has(item.status.toUpperCase()) ? item.count : 0),
    0,
  );
}

function ProviderWorkspace() {
  const [activeId, setActiveId] = useState("overview");
  const overview = usePortalQuery<ProviderOverview>("/portal/provider/overview");
  const data = overview.data;
  const openJobs = data
    ? sumCounts(data.jobs, [
        "DISPATCHING",
        "ASSIGNED",
        "EN_ROUTE",
        "ON_SITE",
        "DIAGNOSING",
        "IN_PROGRESS",
      ])
    : 0;
  const navigation: PortalNavigationItem[] = [
    {
      id: "overview",
      label: "Overview",
      description: "Provider health, work pipeline, and effective platform capabilities.",
    },
    {
      id: "jobs",
      label: "Jobs",
      description: "Scheduled and completed work assigned to your organization.",
      badge: openJobs || undefined,
    },
    {
      id: "workforce",
      label: "Workforce",
      description: "Technicians, contact records, availability state, and skills.",
      badge: data?.workers_total,
    },
    {
      id: "credentials",
      label: "Credentials",
      description: "License and insurance verification evidence and expirations.",
      badge: data?.credentials_expiring_soon || undefined,
    },
    {
      id: "catalog",
      label: "Services & skills",
      description: "The services your company offers and the technicians qualified to deliver them.",
      badge: data?.services_active,
    },
    {
      id: "earnings",
      label: "Earnings",
      description: "Recognized earnings, availability holds, and payout-batch history.",
    },
    {
      id: "onboarding",
      label: "Company profile",
      description: "Business identity, contact information, service coverage, and application status.",
    },
    {
      id: "security",
      label: "Security",
      description: "Effective role, permission, and session controls.",
    },
  ];

  return (
    <PortalApplication
      config={portalRuntime}
      navigation={navigation}
      activeId={activeId}
      onNavigate={setActiveId}
    >
      {activeId === "overview" ? <OverviewPanel query={overview} /> : null}
      {activeId === "jobs" ? <JobsPanel /> : null}
      {activeId === "workforce" ? (
        <WorkforcePanel vendorId={data?.vendor.id ?? null} onChanged={overview.retry} />
      ) : null}
      {activeId === "credentials" ? <CredentialsPanel /> : null}
      {activeId === "catalog" ? <CatalogPanel onChanged={overview.retry} /> : null}
      {activeId === "earnings" ? <EarningsPanel /> : null}
      {activeId === "onboarding" ? (
        <OnboardingPanel overview={data} onChanged={overview.retry} />
      ) : null}
      {activeId === "security" ? <SecurityPanel /> : null}
    </PortalApplication>
  );
}

function OverviewPanel({ query }: { query: ReturnType<typeof usePortalQuery<ProviderOverview>> }) {
  const { data, error, loading, retry } = query;
  if (loading) return <PortalLoading label="Loading provider overview" />;
  if (error) return <PortalError error={error} onRetry={retry} />;
  if (!data) return <PortalEmpty title="Provider profile is not available" />;
  const openJobs = sumCounts(data.jobs, [
    "DISPATCHING",
    "ASSIGNED",
    "EN_ROUTE",
    "ON_SITE",
    "DIAGNOSING",
    "IN_PROGRESS",
  ]);
  const available = data.earnings
    .filter((item) => item.status.toUpperCase() === "AVAILABLE")
    .reduce((total, item) => total + item.amount_minor, 0);
  const currency = data.earnings[0]?.currency ?? "USD";
  return (
    <>
      <section className="portal-metric-grid" aria-label="Provider operating summary">
        <MetricCard label="Open jobs" value={openJobs} detail="Assigned and active work" />
        <MetricCard
          label="Available technicians"
          value={`${data.workers_available}/${data.workers_total}`}
          detail="Current workforce state"
          tone={data.workers_available > 0 ? "success" : "warning"}
        />
        <MetricCard
          label="Verified credentials"
          value={`${data.credentials_verified}/${data.credentials_total}`}
          detail={
            data.credentials_expiring_soon
              ? `${data.credentials_expiring_soon} expire within 30 days`
              : "No near-term expirations"
          }
          tone={data.credentials_expiring_soon ? "warning" : "success"}
        />
        <MetricCard
          label="Available earnings"
          value={formatMoney(available, currency)}
          detail="Before payout batching"
          tone="success"
        />
      </section>
      {data.application?.requested_information ? (
        <PortalNotice title="Additional information requested" tone="warning">
          {data.application.requested_information}
        </PortalNotice>
      ) : null}
      <div className="portal-split">
        <PortalSection
          title="Recent jobs"
          subtitle="The newest assigned work from the canonical job ledger."
        >
          <JobTable jobs={data.recent_jobs} />
        </PortalSection>
        <PortalSection title="Company readiness" subtitle="Effective partner controls and evidence.">
          <dl className="portal-definition-grid">
            <div><dt>Company</dt><dd>{data.vendor.display_name}</dd></div>
            <div><dt>Vendor status</dt><dd><StatusBadge value={data.vendor.status} /></dd></div>
            <div><dt>Application</dt><dd><StatusBadge value={data.application?.status ?? "not started"} /></dd></div>
            <div><dt>Active services</dt><dd>{data.services_active}</dd></div>
            <div><dt>Active skills</dt><dd>{data.skills_active}</dd></div>
            <div><dt>Service radius</dt><dd>{Math.round(data.vendor.service_radius_meters / 1609.344)} miles</dd></div>
          </dl>
        </PortalSection>
      </div>
      <PortalSection
        title="Effective capabilities"
        subtitle="Disabled capabilities are shown truthfully and cannot be bypassed by this portal."
      >
        <CapabilityGrid capabilities={data.capabilities} />
      </PortalSection>
    </>
  );
}

function JobTable({ jobs }: { jobs: Job[] }) {
  const columns: DataColumn<Job>[] = [
    {
      key: "status",
      label: "Status",
      compact: true,
      render: (job) => <StatusBadge value={job.status} />,
    },
    {
      key: "schedule",
      label: "Schedule",
      render: (job) => (
        <span>
          <strong>{formatDate(job.scheduled_start)}</strong>
          <br />
          <small className="portal-muted">Ends {formatDate(job.scheduled_end)}</small>
        </span>
      ),
    },
    {
      key: "service",
      label: "Service",
      render: (job) => <span className="portal-code">{job.service_id}</span>,
    },
    {
      key: "worker",
      label: "Technician",
      render: (job) => (
        <span className="portal-code">{job.worker_id ?? "Unassigned"}</span>
      ),
    },
    {
      key: "job",
      label: "Job ID",
      render: (job) => <span className="portal-code">{job.id}</span>,
    },
  ];
  return (
    <DataTable
      rows={jobs}
      columns={columns}
      rowKey={(job) => job.id}
      emptyTitle="No provider jobs found"
    />
  );
}

function JobsPanel() {
  const [status, setStatus] = useState("ALL");
  const query = usePortalQuery<ListResponse<Job>>("/portal/provider/jobs?limit=200");
  if (query.loading) return <PortalLoading label="Loading jobs" />;
  if (query.error) return <PortalError error={query.error} onRetry={query.retry} />;
  const rows = (query.data?.items ?? []).filter(
    (job) => status === "ALL" || job.status === status,
  );
  const statuses = Array.from(new Set((query.data?.items ?? []).map((job) => job.status))).sort();
  return (
    <PortalSection
      title="Assigned work"
      subtitle={`${query.data?.total ?? 0} jobs are visible to this provider account.`}
      actions={
        <label className="portal-inline">
          <span className="portal-muted">Status</span>
          <select value={status} onChange={(event: ChangeEvent<HTMLSelectElement>) => setStatus(event.target.value)}>
            <option value="ALL">All statuses</option>
            {statuses.map((value) => <option key={value} value={value}>{formatLabel(value)}</option>)}
          </select>
        </label>
      }
    >
      <JobTable jobs={rows} />
    </PortalSection>
  );
}

function WorkforcePanel({ vendorId, onChanged }: { vendorId: string | null; onChanged: () => void }) {
  const query = usePortalQuery<ListResponse<Worker>>("/portal/provider/workers?limit=200");
  const { request } = usePortalSession();
  const [showForm, setShowForm] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [form, setForm] = useState({ first_name: "", last_name: "", email: "", phone: "" });

  async function createWorker(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!vendorId) return;
    setError("");
    setMessage("");
    try {
      await request<Worker>(`/vendors/${vendorId}/workers`, {
        method: "POST",
        body: JSON.stringify({ ...form, skills: [] }),
      });
      setMessage("Technician added to the provider roster.");
      setForm({ first_name: "", last_name: "", email: "", phone: "" });
      setShowForm(false);
      query.retry();
      onChanged();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to add technician");
    }
  }

  const columns: DataColumn<Worker>[] = [
    {
      key: "name",
      label: "Technician",
      render: (worker) => <span><strong>{worker.first_name} {worker.last_name}</strong><br /><small>{worker.email}</small></span>,
    },
    { key: "phone", label: "Phone", render: (worker) => worker.phone },
    { key: "status", label: "Status", compact: true, render: (worker) => <StatusBadge value={worker.status} /> },
    { key: "available", label: "Availability", compact: true, render: (worker) => <StatusBadge value={worker.available ? "available" : "unavailable"} /> },
    { key: "skills", label: "Skills", render: (worker) => String(worker.skills.length) },
    { key: "id", label: "Worker ID", render: (worker) => <span className="portal-code">{worker.id}</span> },
  ];

  return (
    <PortalSection
      title="Technician roster"
      subtitle={`${query.data?.total ?? 0} workers are linked to this provider organization.`}
      actions={<button type="button" onClick={() => setShowForm((value) => !value)}>{showForm ? "Cancel" : "Add technician"}</button>}
    >
      {message ? <PortalNotice title="Roster updated" tone="success">{message}</PortalNotice> : null}
      {error ? <p className="portal-error" role="alert">{error}</p> : null}
      {showForm ? (
        <form className="portal-form-grid" onSubmit={(event: FormEvent<HTMLFormElement>) => void createWorker(event)}>
          <label>First name<input required maxLength={80} value={form.first_name} onChange={(event: ChangeEvent<HTMLInputElement>) => setForm({ ...form, first_name: event.target.value })} /></label>
          <label>Last name<input required maxLength={80} value={form.last_name} onChange={(event: ChangeEvent<HTMLInputElement>) => setForm({ ...form, last_name: event.target.value })} /></label>
          <label>Email<input required type="email" value={form.email} onChange={(event: ChangeEvent<HTMLInputElement>) => setForm({ ...form, email: event.target.value })} /></label>
          <label>Phone<input required minLength={5} maxLength={32} value={form.phone} onChange={(event: ChangeEvent<HTMLInputElement>) => setForm({ ...form, phone: event.target.value })} /></label>
          <div className="portal-form-span"><button className="portal-button portal-button--primary" type="submit">Add technician</button></div>
        </form>
      ) : null}
      {query.loading ? <PortalLoading label="Loading workforce" /> : null}
      {query.error ? <PortalError error={query.error} onRetry={query.retry} /> : null}
      {query.data ? <DataTable rows={query.data.items} columns={columns} rowKey={(worker) => worker.id} emptyTitle="No technicians have been added" /> : null}
    </PortalSection>
  );
}

function CredentialsPanel() {
  const query = usePortalQuery<ListResponse<Credential>>("/portal/provider/credentials?limit=200");
  if (query.loading) return <PortalLoading label="Loading credentials" />;
  if (query.error) return <PortalError error={query.error} onRetry={query.retry} />;
  const rows = query.data?.items ?? [];
  const expiring = rows.filter((item) => {
    const expiry = new Date(`${item.expires_on}T00:00:00Z`).getTime();
    return expiry <= Date.now() + 30 * 24 * 60 * 60 * 1000;
  });
  const columns: DataColumn<Credential>[] = [
    { key: "type", label: "Credential", render: (item) => formatLabel(item.credential_type) },
    { key: "jurisdiction", label: "Jurisdiction", compact: true, render: (item) => item.jurisdiction },
    { key: "reference", label: "Reference", render: (item) => item.reference_last4 ? `•••• ${item.reference_last4}` : "Not recorded" },
    { key: "expiry", label: "Expires", render: (item) => formatDate(item.expires_on) },
    { key: "verified", label: "Verification", compact: true, render: (item) => <StatusBadge value={item.verified ? "verified" : "unverified"} /> },
  ];
  return (
    <PortalSection title="Compliance credentials" subtitle="Sensitive document references are masked. Verification is performed by authorized operations staff.">
      {expiring.length ? <PortalNotice title="Credential attention required" tone="warning">{expiring.length} credential{expiring.length === 1 ? "" : "s"} expire within 30 days or are already expired. Contact BREERO Operations with replacement evidence.</PortalNotice> : null}
      <DataTable rows={rows} columns={columns} rowKey={(item) => item.id} emptyTitle="No credentials are recorded" />
    </PortalSection>
  );
}

function CatalogPanel({ onChanged }: { onChanged: () => void }) {
  const services = usePortalQuery<ListResponse<ProviderService>>("/provider/services?include_inactive=true");
  const skills = usePortalQuery<ListResponse<ProviderSkill>>("/provider/skills?include_inactive=true");
  const catalog = usePortalQuery<Service[]>("/services");
  const workers = usePortalQuery<ListResponse<Worker>>("/portal/provider/workers?limit=200");
  const { request } = usePortalSession();
  const [serviceId, setServiceId] = useState("");
  const [skillId, setSkillId] = useState("");
  const [workerId, setWorkerId] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const assignedServiceIds = new Set((services.data?.items ?? []).map((item) => item.service_id));
  const availableServices = (catalog.data ?? []).filter((item) => !assignedServiceIds.has(item.id));
  const assignedSkillKeys = new Set((skills.data?.items ?? []).map((item) => `${item.worker_id}:${item.skill.id}`));
  const requiredSkills = Array.from(
    new Map(
      (services.data?.items ?? [])
        .flatMap((item) => item.required_skills)
        .map((item) => [item.id, item]),
    ).values(),
  );

  async function addService(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      await request<ProviderService>("/provider/services", {
        method: "POST",
        body: JSON.stringify({ service_id: serviceId, display_order: services.data?.total ?? 0 }),
      });
      setMessage("Service added to the provider catalog.");
      setServiceId("");
      services.retry();
      onChanged();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to add service");
    }
  }

  async function toggleService(service: ProviderService) {
    setError("");
    try {
      await request<ProviderService>(`/provider/services/${service.id}`, {
        method: "PATCH",
        headers: { "If-Match": String(service.version) },
        body: JSON.stringify({ active: !service.active }),
      });
      setMessage(`${service.service_name} ${service.active ? "deactivated" : "activated"}.`);
      services.retry();
      onChanged();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to update service");
    }
  }

  async function addSkill(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (!workerId || !skillId) return;
    if (assignedSkillKeys.has(`${workerId}:${skillId}`)) {
      setError("That technician already has this skill assignment.");
      return;
    }
    try {
      await request<ProviderSkill>("/provider/skills", {
        method: "POST",
        body: JSON.stringify({ skill_id: skillId, worker_id: workerId }),
      });
      setMessage("Skill submitted for the selected technician.");
      setSkillId("");
      skills.retry();
      onChanged();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to add skill");
    }
  }

  const serviceColumns: DataColumn<ProviderService>[] = [
    { key: "service", label: "Service", render: (item) => <span><strong>{item.service_name}</strong><br /><small>{formatLabel(item.service_category)}</small></span> },
    { key: "approval", label: "Approval", compact: true, render: (item) => <StatusBadge value={item.status} /> },
    { key: "active", label: "Offering", compact: true, render: (item) => <StatusBadge value={item.active ? "active" : "inactive"} /> },
    { key: "skills", label: "Required skills", render: (item) => item.required_skills.map((skill) => skill.name).join(", ") || "None" },
    { key: "action", label: "Action", compact: true, render: (item) => <button className="portal-button" type="button" onClick={() => void toggleService(item)}>{item.active ? "Deactivate" : "Activate"}</button> },
  ];
  const skillColumns: DataColumn<ProviderSkill>[] = [
    { key: "skill", label: "Skill", render: (item) => <span><strong>{item.skill.name}</strong><br /><small>{formatLabel(item.skill.category)}</small></span> },
    { key: "worker", label: "Technician", render: (item) => workers.data?.items.find((worker) => worker.id === item.worker_id) ? `${workers.data?.items.find((worker) => worker.id === item.worker_id)?.first_name} ${workers.data?.items.find((worker) => worker.id === item.worker_id)?.last_name}` : item.worker_id },
    { key: "status", label: "Approval", compact: true, render: (item) => <StatusBadge value={item.status} /> },
    { key: "active", label: "State", compact: true, render: (item) => <StatusBadge value={item.active ? "active" : "inactive"} /> },
  ];

  return (
    <div className="portal-stack">
      <PortalSection title="Provider services" subtitle="Only approved catalog services can be offered to customers.">
        {message ? <PortalNotice title="Catalog updated" tone="success">{message}</PortalNotice> : null}
        {error ? <p className="portal-error" role="alert">{error}</p> : null}
        <form className="portal-inline" onSubmit={(event: FormEvent<HTMLFormElement>) => void addService(event)}>
          <select required value={serviceId} onChange={(event: ChangeEvent<HTMLSelectElement>) => setServiceId(event.target.value)}>
            <option value="">Choose an available service</option>
            {availableServices.map((item) => <option key={item.id} value={item.id}>{item.name} · {formatLabel(item.category)}</option>)}
          </select>
          <button className="portal-button portal-button--primary" type="submit" disabled={!serviceId}>Add service</button>
        </form>
        {services.loading ? <PortalLoading label="Loading services" /> : null}
        {services.error ? <PortalError error={services.error} onRetry={services.retry} /> : null}
        {services.data ? <DataTable rows={services.data.items} columns={serviceColumns} rowKey={(item) => item.id} emptyTitle="No services are configured" /> : null}
      </PortalSection>
      <PortalSection title="Technician skills" subtitle="Skill approval remains visible separately from service approval.">
        <form className="portal-form-grid" onSubmit={(event: FormEvent<HTMLFormElement>) => void addSkill(event)}>
          <label>Technician<select required value={workerId} onChange={(event: ChangeEvent<HTMLSelectElement>) => setWorkerId(event.target.value)}><option value="">Choose technician</option>{(workers.data?.items ?? []).map((item) => <option key={item.id} value={item.id}>{item.first_name} {item.last_name}</option>)}</select></label>
          <label>Required skill<select required value={skillId} onChange={(event: ChangeEvent<HTMLSelectElement>) => setSkillId(event.target.value)}><option value="">Choose skill</option>{requiredSkills.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <div className="portal-form-span"><button className="portal-button portal-button--primary" type="submit" disabled={!workerId || !skillId}>Submit skill</button></div>
        </form>
        {skills.loading ? <PortalLoading label="Loading skills" /> : null}
        {skills.error ? <PortalError error={skills.error} onRetry={skills.retry} /> : null}
        {skills.data ? <DataTable rows={skills.data.items} columns={skillColumns} rowKey={(item) => item.id} emptyTitle="No technician skills are configured" /> : null}
      </PortalSection>
    </div>
  );
}

function EarningsPanel() {
  const earnings = usePortalQuery<ListResponse<Earning>>("/portal/provider/earnings?limit=500");
  const payouts = usePortalQuery<ListResponse<PayoutBatch>>("/portal/provider/payout-batches?limit=200");
  const { state } = usePortalSession();
  const rows = useMemo(() => earnings.data?.items ?? [], [earnings.data?.items]);
  const byCurrency = useMemo(() => {
    const result = new Map<string, { available: number; pending: number; paid: number }>();
    for (const item of rows) {
      const current = result.get(item.currency) ?? { available: 0, pending: 0, paid: 0 };
      if (item.status === "AVAILABLE") current.available += item.payable_minor;
      else if (item.status === "PAID") current.paid += item.payable_minor;
      else current.pending += item.payable_minor;
      result.set(item.currency, current);
    }
    return result;
  }, [rows]);
  const primary = Array.from(byCurrency.entries())[0] ?? ["USD", { available: 0, pending: 0, paid: 0 }] as const;
  if (state.status !== "authenticated") return null;
  const earningColumns: DataColumn<Earning>[] = [
    { key: "status", label: "Status", compact: true, render: (item) => <StatusBadge value={item.status} /> },
    { key: "job", label: "Job", render: (item) => <span className="portal-code">{item.job_id}</span> },
    { key: "gross", label: "Gross", render: (item) => formatMoney(item.gross_minor, item.currency) },
    { key: "fees", label: "Fees", render: (item) => formatMoney(item.fee_minor, item.currency) },
    { key: "payable", label: "Payable", render: (item) => <strong>{formatMoney(item.payable_minor, item.currency)}</strong> },
    { key: "available", label: "Available", render: (item) => formatDate(item.available_at) },
    { key: "batch", label: "Payout batch", render: (item) => item.payout_batch_id ? <span className="portal-code">{item.payout_batch_id}</span> : "Not batched" },
  ];
  const payoutColumns: DataColumn<PayoutBatch>[] = [
    { key: "reference", label: "Reference", render: (item) => <strong>{item.reference}</strong> },
    { key: "status", label: "Status", compact: true, render: (item) => <StatusBadge value={item.status} /> },
    { key: "amount", label: "Amount", render: (item) => formatMoney(item.total_minor, item.currency) },
    { key: "earnings", label: "Earnings", render: (item) => item.earning_count },
    { key: "provider", label: "Provider state", render: (item) => item.provider_status ?? "Not submitted" },
    { key: "created", label: "Created", render: (item) => formatDate(item.created_at) },
  ];
  return (
    <div className="portal-stack">
      <section className="portal-metric-grid" aria-label="Earnings summary">
        <MetricCard label="Available" value={formatMoney(primary[1].available, primary[0])} detail="Eligible for future batching" tone="success" />
        <MetricCard label="Pending / held" value={formatMoney(primary[1].pending, primary[0])} detail="Subject to release policy" />
        <MetricCard label="Paid" value={formatMoney(primary[1].paid, primary[0])} detail="Completed earnings" />
        <MetricCard label="Payout execution" value={state.session.capabilities.payouts ? "Enabled" : "Disabled"} detail="Platform capability" tone={state.session.capabilities.payouts ? "success" : "warning"} />
      </section>
      {!state.session.capabilities.payouts ? <PortalNotice title="Payout execution is disabled" tone="warning">Earnings and historical payout batches remain visible. No payout can be created, approved, or submitted from this portal while the production capability is off.</PortalNotice> : null}
      <PortalSection title="Earning ledger" subtitle={`${earnings.data?.total ?? 0} immutable earning records.`}>
        {earnings.loading ? <PortalLoading label="Loading earnings" /> : null}
        {earnings.error ? <PortalError error={earnings.error} onRetry={earnings.retry} /> : null}
        {earnings.data ? <DataTable rows={earnings.data.items} columns={earningColumns} rowKey={(item) => item.id} emptyTitle="No earnings have been recognized" /> : null}
      </PortalSection>
      <PortalSection title="Payout history" subtitle={`${payouts.data?.total ?? 0} batches include this provider's earnings.`}>
        {payouts.loading ? <PortalLoading label="Loading payout history" /> : null}
        {payouts.error ? <PortalError error={payouts.error} onRetry={payouts.retry} /> : null}
        {payouts.data ? <DataTable rows={payouts.data.items} columns={payoutColumns} rowKey={(item) => item.id} emptyTitle="No payout batches are available" /> : null}
      </PortalSection>
    </div>
  );
}

function OnboardingPanel({ overview, onChanged }: { overview: ProviderOverview | null; onChanged: () => void }) {
  const profile = usePortalQuery<Vendor>("/provider/profile");
  const onboarding = usePortalQuery<ProviderApplication>("/provider/onboarding");
  const { request } = usePortalSession();
  const [profileForm, setProfileForm] = useState({ legal_name: "", display_name: "", phone: "", service_radius_meters: "" });
  const [postalCodes, setPostalCodes] = useState("");
  const [profileSeeded, setProfileSeeded] = useState(false);
  const [onboardingSeeded, setOnboardingSeeded] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!profile.data || profileSeeded) return;
    setProfileForm({
      legal_name: profile.data.legal_name,
      display_name: profile.data.display_name,
      phone: profile.data.phone,
      service_radius_meters: String(profile.data.service_radius_meters),
    });
    setProfileSeeded(true);
  }, [profile.data, profileSeeded]);

  useEffect(() => {
    if (!onboarding.data || onboardingSeeded) return;
    setPostalCodes(onboarding.data.postal_codes.join("\n"));
    setOnboardingSeeded(true);
  }, [onboarding.data, onboardingSeeded]);

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      await request<Vendor>("/provider/profile", {
        method: "PATCH",
        body: JSON.stringify({
          legal_name: profileForm.legal_name,
          display_name: profileForm.display_name,
          phone: profileForm.phone,
          service_radius_meters: Number(profileForm.service_radius_meters),
        }),
      });
      setMessage("Company profile saved.");
      profile.retry();
      onChanged();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to save profile");
    }
  }

  async function saveCoverage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const normalized = Array.from(
      new Set(postalCodes.split(/[\s,]+/).map((item) => item.trim()).filter(Boolean)),
    );
    try {
      await request<ProviderApplication>("/provider/onboarding", {
        method: "PATCH",
        body: JSON.stringify({ postal_codes: normalized }),
      });
      setMessage("Service ZIP codes saved to the onboarding record.");
      onboarding.retry();
      onChanged();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to save coverage");
    }
  }

  const application = onboarding.data ?? overview?.application ?? null;
  return (
    <div className="portal-stack">
      {message ? <PortalNotice title="Profile updated" tone="success">{message}</PortalNotice> : null}
      {error ? <p className="portal-error" role="alert">{error}</p> : null}
      <div className="portal-split">
        <PortalSection title="Company identity" subtitle="These details appear in operational and customer-facing records.">
          {profile.loading ? <PortalLoading label="Loading company profile" /> : null}
          {profile.error ? <PortalError error={profile.error} onRetry={profile.retry} /> : null}
          <form className="portal-form-grid" onSubmit={(event: FormEvent<HTMLFormElement>) => void saveProfile(event)}>
            <label>Legal name<input required maxLength={180} value={profileForm.legal_name} onChange={(event: ChangeEvent<HTMLInputElement>) => setProfileForm({ ...profileForm, legal_name: event.target.value })} /></label>
            <label>Display name<input required maxLength={120} value={profileForm.display_name} onChange={(event: ChangeEvent<HTMLInputElement>) => setProfileForm({ ...profileForm, display_name: event.target.value })} /></label>
            <label>Phone<input required minLength={5} maxLength={32} value={profileForm.phone} onChange={(event: ChangeEvent<HTMLInputElement>) => setProfileForm({ ...profileForm, phone: event.target.value })} /></label>
            <label>Service radius (meters)<input required type="number" min={1000} max={500000} value={profileForm.service_radius_meters} onChange={(event: ChangeEvent<HTMLInputElement>) => setProfileForm({ ...profileForm, service_radius_meters: event.target.value })} /></label>
            <div className="portal-form-span"><button className="portal-button portal-button--primary" type="submit">Save company profile</button></div>
          </form>
        </PortalSection>
        <PortalSection title="Application status" subtitle="Review state and outstanding information requests.">
          <dl className="portal-definition-grid">
            <div><dt>Status</dt><dd><StatusBadge value={application?.status ?? "not started"} /></dd></div>
            <div><dt>Version</dt><dd>{application?.version ?? "—"}</dd></div>
            <div><dt>Submitted</dt><dd>{formatDate(application?.submitted_at)}</dd></div>
            <div><dt>Decision</dt><dd>{formatDate(application?.decided_at)}</dd></div>
          </dl>
          {application?.requested_information ? <PortalNotice title="Information requested" tone="warning">{application.requested_information}</PortalNotice> : null}
          {application?.decision_reason ? <PortalNotice title="Decision record" tone={application.status === "REJECTED" ? "danger" : "info"}>{application.decision_reason}</PortalNotice> : null}
        </PortalSection>
      </div>
      <PortalSection title="Service coverage" subtitle="Enter one five-digit ZIP code or ZIP+4 per line. Duplicate values are removed by the API.">
        {onboarding.loading ? <PortalLoading label="Loading onboarding record" /> : null}
        {onboarding.error ? <PortalError error={onboarding.error} onRetry={onboarding.retry} /> : null}
        <form className="portal-form-grid" onSubmit={(event: FormEvent<HTMLFormElement>) => void saveCoverage(event)}>
          <label className="portal-form-span">ZIP codes<textarea value={postalCodes} onChange={(event: ChangeEvent<HTMLTextAreaElement>) => setPostalCodes(event.target.value)} placeholder={"10001\n11201\n33101"} /></label>
          <div className="portal-form-span"><button className="portal-button portal-button--primary" type="submit">Save service coverage</button></div>
        </form>
      </PortalSection>
      {application && ["DRAFT", "NEEDS_INFORMATION"].includes(application.status) ? (
        <PortalSection title="Submit for review" subtitle="Submission freezes the current application version for operations review.">
          <PortalConfirmForm
            title="Submit provider application"
            description="Confirm that company identity, service coverage, credentials, licenses, insurance, services, and technician skills are complete and accurate."
            confirmLabel="Submit application"
            onConfirm={async () => {
              await request<ProviderApplication>("/provider/onboarding/submit", { method: "POST" });
              setMessage("Provider application submitted for review.");
              onboarding.retry();
              onChanged();
            }}
          />
        </PortalSection>
      ) : null}
    </div>
  );
}

function SecurityPanel() {
  const { state } = usePortalSession();
  if (state.status !== "authenticated") return null;
  return (
    <div className="portal-stack">
      <PortalSection title="Access context" subtitle="Resolved by the canonical backend access service after Keycloak sign-in.">
        <dl className="portal-definition-grid">
          <div><dt>Identity</dt><dd>{formatLabel(state.session.context.identity_mode)}</dd></div>
          <div><dt>Roles</dt><dd>{state.session.context.roles.map(formatLabel).join(", ")}</dd></div>
          <div><dt>Departments</dt><dd>{state.session.context.departments.map(formatLabel).join(", ")}</dd></div>
          <div><dt>Vendor scope</dt><dd className="portal-code">{state.session.context.assignments.find((item) => item.vendor_id)?.vendor_id ?? "Resolved by ownership"}</dd></div>
          <div><dt>Permissions</dt><dd>{state.session.context.permissions.length}</dd></div>
          <div><dt>Session expires</dt><dd>{formatDate(new Date(state.session.expires_at * 1000))}</dd></div>
        </dl>
      </PortalSection>
      <PortalSection title="Browser controls" subtitle="Enforced for every portal request.">
        <PortalNotice title="Secure BFF session active" tone="success">Bearer tokens remain in encrypted HTTP-only cookies. The browser calls only same-origin routes, and every state-changing operation requires the per-session CSRF token.</PortalNotice>
        <PortalNotice title="Offline safety" tone="info">Changes are blocked while the browser is offline. Session expiration and sign-out propagate across open tabs.</PortalNotice>
      </PortalSection>
    </div>
  );
}

export default function PartnerPortal() {
  return (
    <PortalSessionProvider>
      <ProviderWorkspace />
    </PortalSessionProvider>
  );
}
