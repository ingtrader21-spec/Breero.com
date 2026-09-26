/**
 * Partner-portal transport. Every provider route derives the provider organization
 * from the bearer token; no method here accepts or sends a vendor identifier.
 */
import type {
  AvailabilityPreview,
  AvailabilityRule,
  AvailabilityRuleInput,
  AvailabilitySnapshot,
  BlackoutInput,
  BlackoutPeriod,
  CatalogService,
  CatalogSkill,
  OfferStatus,
  OnboardingChecklist,
  OnboardingPatch,
  ProfessionalLead,
  ProviderApplication,
  ProviderJob,
  ProviderOffer,
  ProviderProfile,
  ProviderProfilePatch,
  ProviderService,
  ProviderSkill,
  ProviderWorker,
  ProviderWorkerInput,
  Qualification,
  QualificationInput,
  QualificationList,
  Session,
} from "./types";

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly details: string[];

  constructor(status: number, message: string, code?: string, details: string[] = []) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }

  get isVersionConflict(): boolean {
    return this.status === 409 && this.code === "VERSION_CONFLICT";
  }
}

type Fetch = (input: string, init?: RequestInit) => Promise<Response>;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Normalizes v1 DomainError, HTTPException, and validation payloads. */
export async function errorFromResponse(response: Response): Promise<ApiError> {
  const body: unknown = await response.json().catch(() => null);
  const fallback = `Request failed (${response.status})`;
  if (isRecord(body) && isRecord(body.error)) {
    const { code, message } = body.error;
    return new ApiError(
      response.status,
      typeof message === "string" ? message : fallback,
      typeof code === "string" ? code : undefined,
    );
  }
  if (isRecord(body) && typeof body.detail === "string") {
    return new ApiError(response.status, body.detail);
  }
  if (isRecord(body) && isRecord(body.detail)) {
    const code = typeof body.detail.code === "string" ? body.detail.code : undefined;
    const missing = Array.isArray(body.detail.missing)
      ? body.detail.missing.filter((item): item is string => typeof item === "string")
      : [];
    const message = code === "ONBOARDING_INCOMPLETE"
      ? "Complete every onboarding step before submitting."
      : typeof body.detail.message === "string" ? body.detail.message : fallback;
    return new ApiError(response.status, message, code, missing);
  }
  if (isRecord(body) && Array.isArray(body.detail)) {
    const details = body.detail
      .filter(isRecord)
      .map((item) => {
        const location = Array.isArray(item.loc) ? item.loc.filter((part) => part !== "body").join(".") : "";
        const message = typeof item.msg === "string" ? item.msg : "Invalid value";
        return location ? `${location}: ${message}` : message;
      });
    return new ApiError(response.status, "Some fields need attention.", "VALIDATION_ERROR", details);
  }
  return new ApiError(response.status, fallback);
}

export function resolveApiBase(value: string | undefined): string {
  if (!value) throw new Error("A secure API origin is required");
  const trimmed = value.replace(/\/+$/, "");
  if (!/^https:\/\/[^/\s]+/.test(trimmed)) throw new Error("A secure API origin is required");
  return trimmed;
}

const ifMatch = (version: number) => ({ "If-Match": `"${version}"` });

export class PartnerApi {
  private readonly base: string;
  private readonly token: string;
  private readonly fetchImpl: Fetch;
  private readonly onUnauthorized?: () => void;

  constructor(
    base: string,
    token: string,
    options: { fetchImpl?: Fetch; onUnauthorized?: () => void } = {},
  ) {
    this.base = base;
    this.token = token;
    this.fetchImpl = options.fetchImpl ?? ((input, init) => fetch(input, init));
    this.onUnauthorized = options.onUnauthorized;
  }

  async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    if (init.body !== undefined) headers.set("Content-Type", "application/json");
    headers.set("Authorization", `Bearer ${this.token}`);
    const response = await this.fetchImpl(`${this.base}${path}`, { ...init, headers, cache: "no-store" });
    if (response.status === 401) this.onUnauthorized?.();
    if (!response.ok) throw await errorFromResponse(response);
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }

  private send<T>(method: string, path: string, body?: unknown, headers?: Record<string, string>): Promise<T> {
    return this.request<T>(path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  }

  // Company profile and onboarding
  profile() { return this.request<ProviderProfile>("/provider/profile"); }
  updateProfile(patch: ProviderProfilePatch) { return this.send<ProviderProfile>("PATCH", "/provider/profile", patch); }
  onboarding() { return this.request<ProviderApplication>("/provider/onboarding"); }
  onboardingChecklist() { return this.request<OnboardingChecklist>("/provider/onboarding/checklist"); }
  saveOnboarding(patch: OnboardingPatch, version: number) {
    return this.send<ProviderApplication>("PATCH", "/provider/onboarding", patch, ifMatch(version));
  }
  submitOnboarding(version: number) {
    return this.send<ProviderApplication>("POST", "/provider/onboarding/submit", undefined, ifMatch(version));
  }

  // Catalog selections
  catalogServices() { return this.request<CatalogService[]>("/services"); }
  skillCatalog() { return this.request<{ items: CatalogSkill[]; total: number }>("/provider/skill-catalog"); }
  services(includeInactive = false) {
    return this.request<{ items: ProviderService[]; total: number }>(`/provider/services?include_inactive=${includeInactive}`);
  }
  addService(serviceId: string, displayOrder = 0) {
    return this.send<ProviderService>("POST", "/provider/services", { service_id: serviceId, display_order: displayOrder });
  }
  updateService(id: string, patch: { active?: boolean; display_order?: number }, version: number) {
    return this.send<ProviderService>("PATCH", `/provider/services/${encodeURIComponent(id)}`, patch, ifMatch(version));
  }
  removeService(id: string, version: number) {
    return this.send<void>("DELETE", `/provider/services/${encodeURIComponent(id)}`, undefined, ifMatch(version));
  }
  skills(workerId?: string) {
    const query = workerId ? `?worker_id=${encodeURIComponent(workerId)}` : "";
    return this.request<{ items: ProviderSkill[]; total: number }>(`/provider/skills${query}`);
  }
  addSkill(skillId: string, workerId?: string) {
    return this.send<ProviderSkill>("POST", "/provider/skills", workerId ? { skill_id: skillId, worker_id: workerId } : { skill_id: skillId });
  }
  removeSkill(id: string, version: number) {
    return this.send<void>("DELETE", `/provider/skills/${encodeURIComponent(id)}`, undefined, ifMatch(version));
  }

  // Team
  workers() { return this.request<{ items: ProviderWorker[]; total: number }>("/provider/workers"); }
  addWorker(input: ProviderWorkerInput) { return this.send<ProviderWorker>("POST", "/provider/workers", input); }

  // Availability
  availability() { return this.request<AvailabilitySnapshot>("/provider/availability"); }
  availabilityPreview(startsAt: string, endsAt: string) {
    const query = new URLSearchParams({ starts_at: startsAt, ends_at: endsAt });
    return this.request<AvailabilityPreview>(`/provider/availability/preview?${query.toString()}`);
  }
  addRule(input: AvailabilityRuleInput) { return this.send<AvailabilityRule>("POST", "/provider/availability/rules", input); }
  updateRule(id: string, patch: Partial<Omit<AvailabilityRuleInput, "worker_id">>, version: number) {
    return this.send<AvailabilityRule>("PATCH", `/provider/availability/rules/${encodeURIComponent(id)}`, patch, ifMatch(version));
  }
  deleteRule(id: string, version: number) {
    return this.send<void>("DELETE", `/provider/availability/rules/${encodeURIComponent(id)}`, undefined, ifMatch(version));
  }
  addBlackout(input: BlackoutInput) { return this.send<BlackoutPeriod>("POST", "/provider/availability/blackouts", input); }
  deleteBlackout(id: string, version: number) {
    return this.send<void>("DELETE", `/provider/availability/blackouts/${encodeURIComponent(id)}`, undefined, ifMatch(version));
  }

  // Qualifications (metadata only; binary evidence upload is refused by the API)
  qualifications() { return this.request<QualificationList>("/provider/qualifications"); }
  addQualification(input: QualificationInput) { return this.send<Qualification>("POST", "/provider/qualifications", input); }
  updateQualification(id: string, patch: Partial<Omit<QualificationInput, "worker_id" | "qualification_type">>, version: number) {
    return this.send<Qualification>("PATCH", `/provider/qualifications/${encodeURIComponent(id)}`, patch, ifMatch(version));
  }
  submitQualification(id: string, version: number) {
    return this.send<Qualification>("POST", `/provider/qualifications/${encodeURIComponent(id)}/submit`, undefined, ifMatch(version));
  }
  withdrawQualification(id: string, version: number) {
    return this.send<void>("DELETE", `/provider/qualifications/${encodeURIComponent(id)}`, undefined, ifMatch(version));
  }

  // Jobs and offers
  jobs() { return this.request<{ items: ProviderJob[]; total: number }>("/provider/jobs"); }
  offers(status?: OfferStatus) {
    const query = status ? `?status=${encodeURIComponent(status)}` : "";
    return this.request<{ items: ProviderOffer[]; total: number }>(`/provider/offers${query}`);
  }
  /** Read-only; the route is mounted only when paid leads are enabled (404 otherwise). */
  leads() { return this.request<ProfessionalLead[]>("/provider/leads"); }
  decideOffer(id: string, accept: boolean, workerId?: string) {
    return this.send<ProviderOffer>(
      "POST",
      `/provider/offers/${encodeURIComponent(id)}/decision`,
      workerId ? { accept, worker_id: workerId } : { accept },
    );
  }
}

export async function login(base: string, email: string, password: string, fetchImpl: Fetch = (input, init) => fetch(input, init)): Promise<Session> {
  const response = await fetchImpl(`${base}/auth/login`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
    cache: "no-store",
  });
  if (!response.ok) throw await errorFromResponse(response);
  return (await response.json()) as Session;
}
