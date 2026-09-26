import { describe, expect, it } from "vitest";
import { DEFAULT_QUEUE_FILTERS, fromSearchParams, queueFilterErrors, toQueueSearchParams } from "./queue-filters";

const VENDOR = "3f2c9a4e-8d1b-4c6a-9e7f-0a1b2c3d4e5f";

describe("queue filter serialization", () => {
  it("defaults to the first page of active jobs", () => {
    expect(toQueueSearchParams(DEFAULT_QUEUE_FILTERS).toString()).toBe("limit=50&offset=0");
  });

  it("serializes every supported server filter", () => {
    const params = toQueueSearchParams({
      ...DEFAULT_QUEUE_FILTERS,
      statuses: ["CREATED", "OFFERED"],
      vendorId: ` ${VENDOR} `,
      unassignedOnly: true,
      atRiskOnly: true,
      severity: "CRITICAL",
      scheduledFrom: "2026-09-25T08:00",
      limit: 25,
      offset: 50,
    });
    expect(params.getAll("status")).toEqual(["CREATED", "OFFERED"]);
    expect(params.get("vendor_id")).toBe(VENDOR);
    expect(params.get("unassigned_only")).toBe("true");
    expect(params.get("at_risk_only")).toBe("true");
    expect(params.get("severity")).toBe("CRITICAL");
    expect(params.get("scheduled_from")).toBe(new Date("2026-09-25T08:00").toISOString());
    expect(params.get("limit")).toBe("25");
    expect(params.get("offset")).toBe("50");
  });

  it("never sends malformed identifiers and clamps paging to the server bounds", () => {
    const params = toQueueSearchParams({ ...DEFAULT_QUEUE_FILTERS, vendorId: "not-a-uuid", limit: 999, offset: -5 });
    expect(params.has("vendor_id")).toBe(false);
    expect(params.get("limit")).toBe("200");
    expect(params.get("offset")).toBe("0");
  });

  it("round-trips through the page URL and drops unknown values", () => {
    const original = { ...DEFAULT_QUEUE_FILTERS, statuses: ["ASSIGNED" as const], vendorId: VENDOR, severity: "HIGH" as const, scheduledFrom: "2026-09-25T08:30", offset: 100 };
    const restored = fromSearchParams(toQueueSearchParams(original));
    expect(restored).toEqual(original);
    const hostile = fromSearchParams(new URLSearchParams("status=DROP_TABLE&severity=LOW&limit=-4"));
    expect(hostile.statuses).toEqual([]);
    expect(hostile.severity).toBe("");
    expect(hostile.limit).toBe(50);
  });

  it("reports invalid identifiers and inverted windows before any request", () => {
    expect(queueFilterErrors(DEFAULT_QUEUE_FILTERS)).toEqual([]);
    const errors = queueFilterErrors({ ...DEFAULT_QUEUE_FILTERS, workerId: "abc", scheduledFrom: "2026-09-25T10:00", scheduledTo: "2026-09-25T09:00" });
    expect(errors).toEqual(["Worker ID must be a UUID.", "Scheduled 'to' must be after 'from'."]);
  });
});
