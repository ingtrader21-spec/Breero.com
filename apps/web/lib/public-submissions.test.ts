import { describe, expect, it, vi } from "vitest";
import {
  endpointForSubmission,
  prepareSubmissionAttempt,
  stableSerialize,
  submissionErrorFromResponse,
} from "./public-submissions";

describe("public submission client", () => {
  it("serializes equivalent payloads consistently", () => {
    expect(stableSerialize({ b: 2, a: { d: 4, c: 3 } })).toBe(
      stableSerialize({ a: { c: 3, d: 4 }, b: 2 }),
    );
  });

  it("reuses one idempotency key for a same-payload retry", () => {
    const createKey = vi.fn()
      .mockReturnValueOnce("first-key")
      .mockReturnValueOnce("second-key");

    const first = prepareSubmissionAttempt(null, { email: "person@example.com", name: "Person" }, createKey);
    const retry = prepareSubmissionAttempt(first, { name: "Person", email: "person@example.com" }, createKey);

    expect(retry).toBe(first);
    expect(retry.idempotencyKey).toBe("first-key");
    expect(createKey).toHaveBeenCalledTimes(1);
  });

  it("rotates the idempotency key when the payload changes", () => {
    const createKey = vi.fn()
      .mockReturnValueOnce("first-key")
      .mockReturnValueOnce("second-key");

    const first = prepareSubmissionAttempt(null, { message: "Original" }, createKey);
    const changed = prepareSubmissionAttempt(first, { message: "Updated" }, createKey);

    expect(changed.idempotencyKey).toBe("second-key");
    expect(createKey).toHaveBeenCalledTimes(2);
  });

  it("preserves correlation and retry metadata from an API error", async () => {
    const response = new Response(
      JSON.stringify({ error: { code: "RATE_LIMITED", message: "Try again shortly" } }),
      {
        status: 429,
        headers: {
          "content-type": "application/json",
          "retry-after": "60",
          "x-correlation-id": "correlation-123",
        },
      },
    );

    const error = await submissionErrorFromResponse(response);

    expect(error.message).toBe("Try again shortly");
    expect(error.code).toBe("RATE_LIMITED");
    expect(error.retryAfterSeconds).toBe(60);
    expect(error.correlationId).toBe("correlation-123");
  });

  it("maps V1 FastAPI validation arrays into safe field messages", async () => {
    const response = new Response(
      JSON.stringify({
        detail: [
          { type: "string_too_short", loc: ["body", "message"], msg: "String should have at least 10 characters" },
          { type: "value_error", loc: ["body", "service_categories", 0], msg: "Invalid service slug" },
          { type: "ignored", loc: { unexpected: true }, msg: 123 },
        ],
      }),
      {
        status: 422,
        headers: {
          "content-type": "application/json",
          "x-request-id": "request-validation-123",
        },
      },
    );

    const error = await submissionErrorFromResponse(response);

    expect(error.message).toBe("Some details are invalid. Please correct the form and try again.");
    expect(error.fields).toEqual({
      message: ["String should have at least 10 characters"],
      "service_categories.0": ["Invalid service slug"],
      form: ["Invalid value"],
    });
    expect(error.correlationId).toBe("request-validation-123");
  });

  it("sanitizes malformed V2 field maps instead of trusting arbitrary values", async () => {
    const response = new Response(
      JSON.stringify({
        code: "VALIDATION_ERROR",
        message: "Request validation failed.",
        fields: {
          email: ["Enter a valid email", 7, null],
          phone: "Enter a valid phone number",
          ignored: { nested: "not displayed" },
        },
      }),
      { status: 422, headers: { "content-type": "application/json" } },
    );

    const error = await submissionErrorFromResponse(response);

    expect(error.fields).toEqual({
      email: ["Enter a valid email"],
      phone: ["Enter a valid phone number"],
    });
  });

  it("does not expose an upstream 500 message", async () => {
    const response = new Response(
      JSON.stringify({ message: "database password and stack detail" }),
      { status: 500, headers: { "content-type": "application/json" } },
    );

    const error = await submissionErrorFromResponse(response);

    expect(error.message).not.toContain("database password");
    expect(error.status).toBe(500);
  });

  it("maps every public form to a real proxy endpoint", () => {
    expect(endpointForSubmission("service")).toBe("service-requests");
    expect(endpointForSubmission("contact")).toBe("contact");
    expect(endpointForSubmission("provider")).toBe("provider-interest");
  });
});


it("handles inherited-name validation fields without losing the error response", async () => {
  const result = await submissionErrorFromResponse(new Response(JSON.stringify({detail: [{loc: ["body", "constructor"], msg: "Invalid field"}]}), {status: 422}));
  expect(result.fields?.constructor).toEqual(["Invalid field"]);
});

it("discards unsafe upstream trace identifiers", async () => {
  const result = await submissionErrorFromResponse(new Response("{}", {status: 503, headers: {"x-correlation-id": "not a safe trace id"}}));
  expect(result.correlationId).toBeUndefined();
});
