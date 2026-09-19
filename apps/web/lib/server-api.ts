import "server-only";
import { NextRequest, NextResponse } from "next/server";
import { safeTraceId } from "./trace-id";

const DEFAULT_API = "https://api.breero.com/api/v1";
const FORWARDED_RESPONSE_HEADERS = [
  "allow",
  "etag",
  "retry-after",
  "www-authenticate",
  "x-correlation-id",
  "x-request-id",
] as const;

export function serverApiBase(): string {
  return (
    process.env.BREERO_API_INTERNAL_URL
    ?? process.env.NEXT_PUBLIC_API_BASE_URL
    ?? DEFAULT_API
  ).replace(/\/$/, "");
}

function responseHeaders(response: Response): Headers {
  const headers = new Headers();
  for (const name of FORWARDED_RESPONSE_HEADERS) {
    const value = response.headers.get(name);
    if (value && (!name.startsWith("x-") || safeTraceId(value))) headers.set(name, value);
  }
  return headers;
}

function unavailableResponse(request: NextRequest): NextResponse {
  const requestId =
    safeTraceId(request.headers.get("x-correlation-id"))
    ?? safeTraceId(request.headers.get("x-request-id"))
    ?? globalThis.crypto.randomUUID();
  return NextResponse.json(
    {
      error: {
        code: "UPSTREAM_UNAVAILABLE",
        message: "The BREERO service is temporarily unavailable. Please try again.",
      },
    },
    {
      status: 503,
      headers: {
        "retry-after": "15",
        "x-correlation-id": requestId,
        "x-request-id": requestId,
      },
    },
  );
}

export async function proxyApiRequest(
  request: NextRequest,
  path: string,
  init: RequestInit = {},
): Promise<NextResponse> {
  try {
    const response = await fetch(`${serverApiBase()}${path}`, {
      ...init,
      cache: "no-store",
      signal: AbortSignal.timeout(12_000),
    });
    const headers = responseHeaders(response);
    if (response.status === 204) {
      return new NextResponse(null, { status: response.status, headers });
    }

    const contentType = response.headers.get("content-type") ?? "";
    const body = contentType.includes("application/json")
      ? await response.json()
      : { detail: await response.text() };
    return NextResponse.json(body, { status: response.status, headers });
  } catch {
    return unavailableResponse(request);
  }
}

export function forwardedHeaders(request: NextRequest, extra: HeadersInit = {}): Headers {
  const headers = new Headers(extra);
  headers.set("content-type", "application/json");
  const userAgent = request.headers.get("user-agent");
  if (userAgent) headers.set("user-agent", userAgent);
  const forwardedFor = request.headers.get("x-forwarded-for");
  if (forwardedFor) headers.set("x-forwarded-for", forwardedFor);
  const requestId = safeTraceId(request.headers.get("x-request-id"));
  if (requestId) headers.set("x-request-id", requestId);
  const correlationId = safeTraceId(request.headers.get("x-correlation-id"));
  if (correlationId) headers.set("x-correlation-id", correlationId);
  return headers;
}
