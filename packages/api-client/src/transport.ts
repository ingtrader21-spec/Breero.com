import { ApiError, apiErrorFromResponse } from "./errors";

export type AccessTokenProvider = () => string | null | Promise<string | null>;
export interface TransportOptions { baseUrl: string; timeoutMs?: number; getAccessToken?: AccessTokenProvider; refreshAccessToken?: () => Promise<string | null>; fetch?: typeof globalThis.fetch; onUnauthorized?: () => void }
export interface RequestOptions extends Omit<RequestInit, "body"> { body?: unknown; timeoutMs?: number; retry?: boolean }
export interface Transport { request<T>(path: string, options?: RequestOptions): Promise<T> }

const IDEMPOTENT = new Set(["GET", "HEAD", "OPTIONS"]);
const delay = (ms: number, signal: AbortSignal) => new Promise<void>((resolve, reject) => {
  const id = setTimeout(resolve, ms);
  signal.addEventListener("abort", () => { clearTimeout(id); reject(signal.reason); }, { once: true });
});

export class ApiTransport implements Transport {
  private readonly fetcher: typeof globalThis.fetch;
  constructor(private readonly options: TransportOptions) {
    if (options.baseUrl && !/^https?:\/\//.test(options.baseUrl)) throw new Error("API base URL must be an absolute HTTP(S) URL");
    // Browser implementations of `window.fetch` require Window as their
    // receiver. Preserve receiver-free calls for injected test/adaptor
    // functions, but bind the native global implementation.
    const customFetch = options.fetch;
    this.fetcher = customFetch
      ? (...args) => customFetch(...args)
      : globalThis.fetch.bind(globalThis);
  }

  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const method = (options.method ?? "GET").toUpperCase();
    const canRetry = (options.retry ?? true) && IDEMPOTENT.has(method);
    let lastError: unknown;
    for (let attempt = 0; attempt <= (canRetry ? 2 : 0); attempt += 1) {
      if (attempt > 0) await delay(150 * 2 ** (attempt - 1), options.signal ?? new AbortController().signal);
      try { return await this.execute<T>(path, method, options); }
      catch (error) {
        lastError = error;
        if (error instanceof ApiError && error.kind === "authentication" && this.options.refreshAccessToken && options.retry !== false) {
          const token = await this.options.refreshAccessToken();
          if (token) return this.execute<T>(path, method, { ...options, retry: false });
          this.options.onUnauthorized?.();
        }
        if (!(error instanceof ApiError) || !["network", "server", "unavailable"].includes(error.kind)) throw error;
      }
    }
    throw lastError;
  }

  private async execute<T>(path: string, method: string, options: RequestOptions): Promise<T> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort("timeout"), options.timeoutMs ?? this.options.timeoutMs ?? 12_000);
    const abort = () => controller.abort(options.signal?.reason);
    options.signal?.addEventListener("abort", abort, { once: true });
    try {
      const token = await this.options.getAccessToken?.();
      const headers = new Headers(options.headers);
      headers.set("Accept", "application/json");
      if (options.body !== undefined) headers.set("Content-Type", "application/json");
      if (token) headers.set("Authorization", `Bearer ${token}`);
      if (typeof document !== "undefined" && !IDEMPOTENT.has(method)) {
        const csrf = document.cookie.split("; ").find((item) => item.startsWith("breero_csrf="))?.split("=")[1];
        if (csrf) headers.set("X-CSRF-Token", decodeURIComponent(csrf));
        if (this.options.baseUrl && new URL(this.options.baseUrl).origin !== window.location.origin) {
          const csrfResponse = await this.fetcher(`${this.options.baseUrl.replace(/\/$/, "")}/auth/csrf`, {
            credentials: "include", cache: "no-store", signal: controller.signal,
          });
          if (csrfResponse.ok) {
            const body = await csrfResponse.json() as { csrf_token: string };
            headers.set("X-CSRF-Token", body.csrf_token);
          } else if (csrfResponse.status !== 401) {
            throw await apiErrorFromResponse(csrfResponse);
          }
        }
      }
      const url = this.options.baseUrl ? `${this.options.baseUrl.replace(/\/$/, "")}/${path.replace(/^\//, "")}` : path;
      const response = await this.fetcher(url, { ...options, credentials: "include", method, headers, body: options.body === undefined ? undefined : JSON.stringify(options.body), signal: controller.signal });
      if (!response.ok) {
        const error = await apiErrorFromResponse(response);
        throw error;
      }
      if (response.status === 204) return undefined as T;
      return await response.json() as T;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      if (controller.signal.aborted) throw new ApiError(controller.signal.reason === "timeout" ? "Request timed out" : "Request cancelled", controller.signal.reason === "timeout" ? "timeout" : "cancelled");
      throw new ApiError("Unable to reach BREERO", "network", undefined, undefined, undefined, error);
    } finally {
      clearTimeout(timeout);
      options.signal?.removeEventListener("abort", abort);
    }
  }
}

export class FetchTransport extends ApiTransport {}
