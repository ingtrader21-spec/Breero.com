import { safeTraceId } from "./trace-id";

export type PublicSubmissionKind = "service" | "contact" | "provider";

export type SubmissionAttempt = {
  idempotencyKey: string;
  serializedPayload: string;
};

export type SubmissionErrorDetails = {
  status: number;
  code?: string;
  correlationId?: string;
  retryAfterSeconds?: number;
  fields?: Record<string, string[]>;
};

export class PublicSubmissionError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly correlationId?: string;
  readonly retryAfterSeconds?: number;
  readonly fields?: Record<string, string[]>;

  constructor(message: string, details: SubmissionErrorDetails) {
    super(message);
    this.name = "PublicSubmissionError";
    this.status = details.status;
    this.code = details.code;
    this.correlationId = details.correlationId;
    this.retryAfterSeconds = details.retryAfterSeconds;
    this.fields = details.fields;
  }
}

function canonicalize(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    const result: Record<string, unknown> = Object.create(null);
    for (const key of Object.keys(record).sort()) {
      if (record[key] !== undefined) result[key] = canonicalize(record[key]);
    }
    return result;
  }
  return value;
}

export function stableSerialize(value: unknown): string {
  const serialized = JSON.stringify(canonicalize(value));
  if (serialized === undefined) {
    throw new TypeError("Submission payload must be JSON serializable.");
  }
  return serialized;
}

export function prepareSubmissionAttempt(
  previous: SubmissionAttempt | null,
  payload: unknown,
  createKey: () => string = () => globalThis.crypto.randomUUID(),
): SubmissionAttempt {
  const serializedPayload = stableSerialize(payload);
  if (previous?.serializedPayload === serializedPayload) return previous;
  return { serializedPayload, idempotencyKey: createKey() };
}

function stringValue(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function fieldMap(value: unknown): Record<string, string[]> | undefined {
  if (!value || typeof value !== "object" || Array.isArray(value)) return undefined;
  const fields: Record<string, string[]> = Object.create(null);
  for (const [key, rawMessages] of Object.entries(value as Record<string, unknown>)) {
    const messages = Array.isArray(rawMessages)
      ? rawMessages.map(stringValue).filter((item): item is string => item !== undefined)
      : [stringValue(rawMessages)].filter((item): item is string => item !== undefined);
    if (messages.length) fields[key] = messages;
  }
  return Object.keys(fields).length ? fields : undefined;
}

function fastApiValidationFields(value: unknown): Record<string, string[]> | undefined {
  if (!Array.isArray(value)) return undefined;
  const fields: Record<string, string[]> = Object.create(null);
  for (const item of value.slice(0, 20)) {
    if (!item || typeof item !== "object" || Array.isArray(item)) continue;
    const record = item as Record<string, unknown>;
    const location = Array.isArray(record.loc)
      ? record.loc
          .filter((part) => typeof part === "string" || typeof part === "number")
          .filter((part) => part !== "body")
          .map(String)
          .join(".")
      : "";
    const field = location || "form";
    const message = stringValue(record.msg) ?? "Invalid value";
    (fields[field] ??= []).push(message);
  }
  return Object.keys(fields).length ? fields : undefined;
}

function errorEnvelope(body: unknown): {
  code?: string;
  message?: string;
  fields?: Record<string, string[]>;
} {
  if (!body || typeof body !== "object" || Array.isArray(body)) return {};
  const record = body as Record<string, unknown>;
  const nested = record.error && typeof record.error === "object" && !Array.isArray(record.error)
    ? record.error as Record<string, unknown>
    : undefined;
  const detail = record.detail && typeof record.detail === "object" && !Array.isArray(record.detail)
    ? record.detail as Record<string, unknown>
    : undefined;

  const fields = fieldMap(record.fields ?? nested?.fields ?? detail?.fields)
    ?? fastApiValidationFields(record.detail);

  return {
    code: stringValue(record.code) ?? stringValue(nested?.code) ?? stringValue(detail?.code),
    message:
      stringValue(record.message)
      ?? stringValue(nested?.message)
      ?? stringValue(detail?.message)
      ?? stringValue(record.detail),
    fields,
  };
}

function defaultMessage(status: number): string {
  switch (status) {
    case 400:
      return "Please review the form and try again.";
    case 409:
      return "This request conflicts with an earlier submission. Review the details and retry.";
    case 422:
      return "Some details are invalid. Please correct the form and try again.";
    case 429:
      return "Too many requests were submitted. Please try again shortly.";
    case 503:
      return "BREERO is temporarily unavailable. Your information is still in the form; please retry shortly.";
    default:
      return status >= 500
        ? "BREERO could not accept the request right now. Your information is still in the form; please retry."
        : "BREERO could not accept the request. Please review the form and retry.";
  }
}

function retryAfterSeconds(response: Response): number | undefined {
  const raw = response.headers.get("retry-after");
  if (!raw) return undefined;
  const seconds = Number.parseInt(raw, 10);
  return Number.isFinite(seconds) && seconds >= 0 ? seconds : undefined;
}

export async function submissionErrorFromResponse(response: Response): Promise<PublicSubmissionError> {
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = undefined;
  }

  const envelope = errorEnvelope(body);
  const safeBackendMessage = response.status < 500 ? envelope.message : undefined;
  return new PublicSubmissionError(safeBackendMessage ?? defaultMessage(response.status), {
    status: response.status,
    code: envelope.code,
    fields: envelope.fields,
    retryAfterSeconds: retryAfterSeconds(response),
    correlationId:
      safeTraceId(response.headers.get("x-correlation-id"))
      ?? safeTraceId(response.headers.get("x-request-id"))
      ?? undefined,
  });
}

export function endpointForSubmission(kind: PublicSubmissionKind): string {
  switch (kind) {
    case "service":
      return "service-requests";
    case "contact":
      return "contact";
    case "provider":
      return "provider-interest";
  }
}
