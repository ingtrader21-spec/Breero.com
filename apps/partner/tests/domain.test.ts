import { describe, expect, it } from "vitest";

import {
  groupRulesByWeekday,
  isValidTimeZone,
  validateBlackoutDraft,
  validateRuleDraft,
  zonedLocalToUtcIso,
} from "../lib/availability";
import {
  applicationStatusView,
  buildOnboardingPatch,
  completionPercent,
  formFromApplication,
  ONBOARDING_STEPS,
  parsePostalCodes,
  stepComplete,
} from "../lib/onboarding";
import {
  canEditQualification,
  canSubmitQualification,
  emptyQualificationDraft,
  qualificationStatusView,
  validateQualificationDraft,
} from "../lib/qualifications";
import { readSession, SESSION_KEY, writeSession } from "../lib/session";
import type { ApplicationStatus, AvailabilityRule } from "../lib/types";
import { application } from "./fixtures";

describe("onboarding", () => {
  it("describes every application status", () => {
    const statuses: ApplicationStatus[] = ["DRAFT", "PENDING", "INFORMATION_REQUESTED", "APPROVED", "REJECTED"];
    const views = statuses.map(applicationStatusView);
    expect(views.map((view) => view.tone)).toEqual(["neutral", "info", "warning", "success", "danger"]);
    for (const view of views) expect(view.message.length).toBeGreaterThan(10);
  });

  it("parses ZIP and ZIP+4 codes and flags invalid tokens", () => {
    expect(parsePostalCodes("77001, 77002-1234 77001;abc 1234")).toEqual({
      codes: ["77001", "77002-1234"],
      invalid: ["abc", "1234"],
    });
  });

  it("builds a patch without catalog, availability, or credential fields", () => {
    const previous = application();
    const form = { ...formFromApplication(previous), postalCodes: "77001 77002", dailyJobs: "3", taxIdLast4: "1234", yearsInBusiness: "7" };
    const { patch, errors } = buildOnboardingPatch(form, previous);
    expect(errors).toEqual([]);
    expect(Object.keys(patch).sort()).toEqual(["business", "capacity", "contact_details", "identity", "postal_codes", "service_areas"]);
    expect(patch.business).toMatchObject({ internal_note: "kept", tax_id_last4: "1234", years_in_business: 7 });
    expect(patch.service_areas).toEqual([{ type: "ZIP", value: "77001" }, { type: "ZIP", value: "77002" }]);
    expect(patch.capacity).toEqual({ daily_jobs: 3 });
  });

  it("rejects unsafe or malformed wizard values", () => {
    const previous = application();
    const form = { ...formFromApplication(previous), postalCodes: "7700", taxIdLast4: "12-34-5678", dailyJobs: "0", crewSize: "two" };
    const { errors } = buildOnboardingPatch(form, previous);
    expect(errors).toHaveLength(4);
  });

  it("tracks step completion from the server checklist", () => {
    const checklist = { missing: ["services", "insurance"] };
    const services = ONBOARDING_STEPS.find((step) => step.key === "services");
    const identity = ONBOARDING_STEPS.find((step) => step.key === "identity");
    expect(services && stepComplete(services, checklist)).toBe(false);
    expect(identity && stepComplete(identity, checklist)).toBe(true);
    expect(completionPercent(checklist)).toBe(78);
    expect(completionPercent({ missing: [] })).toBe(100);
  });
});

describe("availability", () => {
  it("validates weekly windows", () => {
    const base = { weekday: "2", startTime: "08:00", endTime: "17:00", timezone: "America/Chicago", validFrom: "", validUntil: "", workerId: "" };
    expect(validateRuleDraft(base).input).toEqual({
      weekday: 2,
      start_time: "08:00",
      end_time: "17:00",
      timezone: "America/Chicago",
      valid_from: null,
      valid_until: null,
    });
    expect(validateRuleDraft({ ...base, startTime: "22:00", endTime: "02:00" }).errors[0]).toMatch(/overnight/);
    expect(validateRuleDraft({ ...base, timezone: "Chicago" }).errors).toHaveLength(1);
    expect(validateRuleDraft({ ...base, validFrom: "2026-12-01", validUntil: "2026-01-01" }).errors).toHaveLength(1);
    expect(validateRuleDraft({ ...base, workerId: "w-1" }).input?.worker_id).toBe("w-1");
  });

  it("converts local wall time to UTC across daylight-saving changes", () => {
    expect(zonedLocalToUtcIso("2026-03-01T09:00", "America/Chicago")).toBe("2026-03-01T15:00:00.000Z");
    expect(zonedLocalToUtcIso("2026-03-08T09:00", "America/Chicago")).toBe("2026-03-08T14:00:00.000Z");
    // Nonexistent spring-forward time resolves forward (03:30 CDT).
    expect(zonedLocalToUtcIso("2026-03-08T02:30", "America/Chicago")).toBe("2026-03-08T08:30:00.000Z");
    // Ambiguous fall-back time resolves to the first occurrence (CDT).
    expect(zonedLocalToUtcIso("2026-11-01T01:30", "America/Chicago")).toBe("2026-11-01T06:30:00.000Z");
    expect(zonedLocalToUtcIso("2026-07-04T12:00", "UTC")).toBe("2026-07-04T12:00:00.000Z");
  });

  it("validates blackout periods and emits offset-bearing UTC values", () => {
    const draft = { startsAt: "2026-11-26T00:00", endsAt: "2026-11-27T00:00", timezone: "America/Chicago", reason: " Holiday ", workerId: "" };
    expect(validateBlackoutDraft(draft).input).toEqual({
      starts_at: "2026-11-26T06:00:00.000Z",
      ends_at: "2026-11-27T06:00:00.000Z",
      timezone: "America/Chicago",
      reason: "Holiday",
    });
    expect(validateBlackoutDraft({ ...draft, endsAt: "2026-11-25T00:00" }).errors).toHaveLength(1);
    expect(validateBlackoutDraft({ ...draft, endsAt: "2028-01-01T00:00" }).errors).toHaveLength(1);
    expect(validateBlackoutDraft({ ...draft, timezone: "Nowhere/City" }).errors).toHaveLength(1);
  });

  it("recognises IANA zones and groups rules Monday-first", () => {
    expect(isValidTimeZone("America/New_York")).toBe(true);
    expect(isValidTimeZone("EST5EDT-invalid")).toBe(false);
    const rule = (weekday: number, start: string): AvailabilityRule => ({
      id: `${weekday}-${start}`, version: 1, worker_id: null, weekday, start_time: start, end_time: "23:00:00",
      timezone: "UTC", valid_from: null, valid_until: null,
    });
    const grouped = groupRulesByWeekday([rule(6, "10:00:00"), rule(0, "13:00:00"), rule(0, "08:00:00")]);
    expect(grouped).toHaveLength(7);
    expect(grouped[0].map((item) => item.start_time)).toEqual(["08:00:00", "13:00:00"]);
    expect(grouped[6]).toHaveLength(1);
  });
});

describe("qualifications", () => {
  it("maps lifecycle to status and allowed actions", () => {
    expect(qualificationStatusView({ status: "SUBMITTED", review_status: "PENDING_REVIEW", is_expired: false }).label).toBe("Pending review");
    expect(qualificationStatusView({ status: "DRAFT", review_status: "NOT_SUBMITTED", is_expired: true }).tone).toBe("danger");
    expect(canEditQualification({ status: "SUBMITTED", review_status: "PENDING_REVIEW" })).toBe(false);
    expect(canEditQualification({ status: "SUBMITTED", review_status: "APPROVED" })).toBe(false);
    expect(canEditQualification({ status: "SUBMITTED", review_status: "INFORMATION_REQUESTED" })).toBe(true);
    expect(canSubmitQualification({ status: "DRAFT", is_expired: false })).toBe(true);
    expect(canSubmitQualification({ status: "DRAFT", is_expired: true })).toBe(false);
  });

  it("refuses links, full reference numbers, and missing expiry", () => {
    const draft = { ...emptyQualificationDraft(), title: "Master plumber", expiresOn: "2027-01-01", jurisdiction: "tx" };
    expect(validateQualificationDraft(draft, "2026-09-25").input).toMatchObject({ jurisdiction: "TX", qualification_type: "LICENSE" });
    expect(validateQualificationDraft({ ...draft, evidenceReference: "https://evil.test/x.pdf" }, "2026-09-25").errors).toHaveLength(1);
    expect(validateQualificationDraft({ ...draft, referenceLast4: "123456789" }, "2026-09-25").errors).toHaveLength(1);
    expect(validateQualificationDraft({ ...draft, expiresOn: "" }, "2026-09-25").errors).toHaveLength(1);
    expect(validateQualificationDraft({ ...draft, expiresOn: "2026-01-01" }, "2026-09-25").errors).toHaveLength(1);
    expect(validateQualificationDraft({ ...draft, qualificationType: "TRAINING", expiresOn: "" }, "2026-09-25").errors).toEqual([]);
  });
});

describe("session storage", () => {
  function memory() {
    const values = new Map<string, string>();
    return {
      values,
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => void values.set(key, value),
      removeItem: (key: string) => void values.delete(key),
    };
  }

  it("accepts only provider sessions and clears anything else", () => {
    const storage = memory();
    writeSession(storage, { access_token: "t", user: { email: "p@x.test", full_name: "P", role: "vendor_admin" } });
    expect(readSession(storage)?.access_token).toBe("t");
    storage.setItem(SESSION_KEY, JSON.stringify({ access_token: "t", user: { email: "c@x.test", full_name: "C", role: "customer" } }));
    expect(readSession(storage)).toBeNull();
    expect(storage.values.has(SESSION_KEY)).toBe(false);
    storage.setItem(SESSION_KEY, "{not json");
    expect(readSession(storage)).toBeNull();
  });
});
