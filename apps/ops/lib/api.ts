import { toQueueSearchParams, type QueueFilterState } from "./queue-filters";
import type {
  AssignmentCandidates,
  AssignmentRead,
  CapacityBoard,
  ExceptionQueue,
  IntegrationFailurePage,
  JobControlDetail,
  JobRead,
  JobStatus,
  OfferRead,
  OperationsDashboard,
  OpsSession,
  QueuePage,
  ReassignmentRead,
  RiskSeverity,
  ServiceAreaProjection,
  WorkRequest,
} from "./types";

export class OpsApiError extends Error {
  constructor(message: string, readonly status: number, readonly code?: string) {
    super(message);
    this.name = "OpsApiError";
  }
}

/** Extract the server's own message from any V1 error envelope. */
export async function errorFromResponse(response: Response): Promise<OpsApiError> {
  const parsed: unknown = await response.json().catch(() => null);
  const body = parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : {};
  const nested = body.error && typeof body.error === "object" ? (body.error as Record<string, unknown>) : {};
  const detail = body.detail;
  let message = `Request failed (${response.status})`;
  if (typeof nested.message === "string") message = nested.message;
  else if (typeof detail === "string") message = detail;
  else if (Array.isArray(detail)) {
    message = detail
      .map((item) => (item && typeof item === "object" && typeof (item as { msg?: unknown }).msg === "string" ? (item as { msg: string }).msg : "Invalid value"))
      .join("; ");
  } else if (typeof body.message === "string") message = body.message;
  return new OpsApiError(message, response.status, typeof nested.code === "string" ? nested.code : undefined);
}

export interface OpsApiOptions {
  baseUrl: string;
  token?: string;
  fetch?: typeof globalThis.fetch;
  onUnauthorized?: () => void;
}

const CONTROL = "/operations/control-center";
const segment = (value: string) => encodeURIComponent(value);

export function createOpsApi(options: OpsApiOptions) {
  const fetcher = options.fetch ?? globalThis.fetch.bind(globalThis);

  async function request<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
    const headers = new Headers({ Accept: "application/json" });
    if (init.body !== undefined) headers.set("Content-Type", "application/json");
    if (options.token) headers.set("Authorization", `Bearer ${options.token}`);
    let response: Response;
    try {
      response = await fetcher(`${options.baseUrl}${path}`, {
        method: init.method ?? "GET",
        headers,
        body: init.body === undefined ? undefined : JSON.stringify(init.body),
        cache: "no-store",
      });
    } catch {
      throw new OpsApiError("Unable to reach the BREERO API", 0);
    }
    if (!response.ok) {
      const error = await errorFromResponse(response);
      if (response.status === 401) options.onUnauthorized?.();
      throw error;
    }
    if (response.status === 204) return undefined as T;
    try {
      return (await response.json()) as T;
    } catch {
      throw new OpsApiError("The BREERO API returned an unreadable response", response.status);
    }
  }

  return {
    login: (email: string, password: string) =>
      request<OpsSession & { refresh_token?: string }>("/auth/login", { method: "POST", body: { email, password } }),
    dashboard: () => request<OperationsDashboard>(`${CONTROL}/summary`),
    queue: (filters: QueueFilterState) => request<QueuePage>(`${CONTROL}/queue?${toQueueSearchParams(filters)}`),
    exceptions: (severity?: RiskSeverity) =>
      request<ExceptionQueue>(`${CONTROL}/exceptions${severity ? `?severity=${severity}` : ""}`),
    capacity: (date?: string, includeInactive = false) => {
      const params = new URLSearchParams();
      if (date) params.set("date", date);
      if (includeInactive) params.set("include_inactive", "true");
      const query = params.toString();
      return request<CapacityBoard>(`${CONTROL}/capacity${query ? `?${query}` : ""}`);
    },
    serviceAreas: () => request<ServiceAreaProjection>(`${CONTROL}/service-areas`),
    integrationFailures: () => request<IntegrationFailurePage>(`${CONTROL}/integration-failures`),
    jobDetail: (jobId: string) => request<JobControlDetail>(`${CONTROL}/jobs/${segment(jobId)}`),
    candidates: (jobId: string) => request<AssignmentCandidates>(`${CONTROL}/jobs/${segment(jobId)}/candidates`),
    match: (jobId: string) => request<OfferRead[]>(`/operations/jobs/${segment(jobId)}/match`, { method: "POST" }),
    assign: (jobId: string, body: { vendor_id: string; worker_id: string; reason: string }) =>
      request<AssignmentRead>(`/operations/jobs/${segment(jobId)}/assign`, { method: "POST", body }),
    reassign: (jobId: string, body: { vendor_id: string; worker_id: string; reason: string; expected_version: number }) =>
      request<ReassignmentRead>(`/operations/jobs/${segment(jobId)}/reassign`, { method: "POST", body }),
    transition: (jobId: string, status: JobStatus, reason: string) =>
      request<JobRead>(`/jobs/${segment(jobId)}/transition`, { method: "POST", body: { status, reason } }),
    reviewWorkRequest: (requestId: string, approve: boolean) =>
      request<WorkRequest>(`/jobs/work-requests/${segment(requestId)}/review`, { method: "POST", body: { approve } }),
  };
}

export type OpsApi = ReturnType<typeof createOpsApi>;
