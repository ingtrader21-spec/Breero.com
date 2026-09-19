import { describe, expect, it } from "vitest";
import { safeTraceId } from "./trace-id";

describe("safeTraceId", () => {
  it("accepts the bounded trace format used by the API", () => {
    expect(safeTraceId("request-123:child_4.5")).toBe("request-123:child_4.5");
    expect(safeTraceId("a".repeat(128))).toBe("a".repeat(128));
  });

  it("rejects empty, oversized, whitespace, and header-injection values", () => {
    expect(safeTraceId(undefined)).toBeUndefined();
    expect(safeTraceId(null)).toBeUndefined();
    expect(safeTraceId("")).toBeUndefined();
    expect(safeTraceId("contains spaces")).toBeUndefined();
    expect(safeTraceId(`valid\r\ninjected: value`)).toBeUndefined();
    expect(safeTraceId("a".repeat(129))).toBeUndefined();
  });
});
