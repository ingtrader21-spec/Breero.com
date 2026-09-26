import type { AvailabilityRule, AvailabilityRuleInput, BlackoutInput } from "./types";

/** ISO order used by the API: Monday = 0 … Sunday = 6. */
export const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"] as const;

const TIME_RE = /^([01]\d|2[0-3]):[0-5]\d$/;
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const LOCAL_DATETIME_RE = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/;

export function isValidTimeZone(zone: string): boolean {
  if (!zone || !(zone === "UTC" || zone.includes("/"))) return false;
  try {
    new Intl.DateTimeFormat("en-US", { timeZone: zone });
    return true;
  } catch {
    return false;
  }
}

export function browserTimeZone(): string {
  try {
    const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    return isValidTimeZone(zone) ? zone : "America/Chicago";
  } catch {
    return "America/Chicago";
  }
}

export interface RuleDraft {
  weekday: string;
  startTime: string;
  endTime: string;
  timezone: string;
  validFrom: string;
  validUntil: string;
  workerId: string;
}

export function validateRuleDraft(draft: RuleDraft): { input?: AvailabilityRuleInput; errors: string[] } {
  const errors: string[] = [];
  const weekday = Number.parseInt(draft.weekday, 10);
  if (!(weekday >= 0 && weekday <= 6)) errors.push("Choose a weekday.");
  if (!TIME_RE.test(draft.startTime) || !TIME_RE.test(draft.endTime)) errors.push("Use HH:MM times.");
  else if (draft.startTime >= draft.endTime) errors.push("Start must be before end. Split overnight hours across two days.");
  if (!isValidTimeZone(draft.timezone)) errors.push("Choose a valid IANA timezone, for example America/Chicago.");
  if (draft.validFrom && !DATE_RE.test(draft.validFrom)) errors.push("Start date must be YYYY-MM-DD.");
  if (draft.validUntil && !DATE_RE.test(draft.validUntil)) errors.push("End date must be YYYY-MM-DD.");
  if (draft.validFrom && draft.validUntil && draft.validFrom > draft.validUntil) errors.push("Start date must not be after end date.");
  if (errors.length) return { errors };
  return {
    errors,
    input: {
      weekday,
      start_time: draft.startTime,
      end_time: draft.endTime,
      timezone: draft.timezone,
      valid_from: draft.validFrom || null,
      valid_until: draft.validUntil || null,
      ...(draft.workerId ? { worker_id: draft.workerId } : {}),
    },
  };
}

/** Offset (ms) of `zone` from UTC at the given instant. */
function zoneOffsetMs(instant: number, zone: string): number {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: zone,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).formatToParts(new Date(instant));
  const value = (type: string) => Number(parts.find((part) => part.type === type)?.value ?? 0);
  const asUtc = Date.UTC(value("year"), value("month") - 1, value("day"), value("hour"), value("minute"), value("second"));
  return asUtc - instant;
}

/**
 * Converts a wall-clock `YYYY-MM-DDTHH:MM` in `zone` into a UTC ISO string. Times that
 * do not exist (spring-forward gap) resolve forward, matching the API's behaviour.
 */
export function zonedLocalToUtcIso(local: string, zone: string): string {
  const match = LOCAL_DATETIME_RE.exec(local);
  if (!match || !isValidTimeZone(zone)) throw new Error("Invalid local date/time or timezone");
  const [, year, month, day, hour, minute] = match.map(Number);
  const wallAsUtc = Date.UTC(year, month - 1, day, hour, minute);
  let instant = wallAsUtc - zoneOffsetMs(wallAsUtc, zone);
  const corrected = wallAsUtc - zoneOffsetMs(instant, zone);
  if (corrected !== instant) instant = Math.max(instant, corrected);
  return new Date(instant).toISOString();
}

export interface BlackoutDraft { startsAt: string; endsAt: string; timezone: string; reason: string; workerId: string }

export function validateBlackoutDraft(draft: BlackoutDraft): { input?: BlackoutInput; errors: string[] } {
  const errors: string[] = [];
  if (!isValidTimeZone(draft.timezone)) errors.push("Choose a valid IANA timezone.");
  if (!LOCAL_DATETIME_RE.test(draft.startsAt) || !LOCAL_DATETIME_RE.test(draft.endsAt)) errors.push("Enter a start and end date/time.");
  if (errors.length) return { errors };
  const startsAt = zonedLocalToUtcIso(draft.startsAt, draft.timezone);
  const endsAt = zonedLocalToUtcIso(draft.endsAt, draft.timezone);
  if (startsAt >= endsAt) errors.push("The blackout must end after it starts.");
  if (Date.parse(endsAt) - Date.parse(startsAt) > 366 * 24 * 3600 * 1000) errors.push("Blackouts may not exceed 366 days.");
  if (draft.reason.length > 500) errors.push("Reason must be 500 characters or fewer.");
  if (errors.length) return { errors };
  return {
    errors,
    input: {
      starts_at: startsAt,
      ends_at: endsAt,
      timezone: draft.timezone,
      reason: draft.reason.trim() || null,
      ...(draft.workerId ? { worker_id: draft.workerId } : {}),
    },
  };
}

export function formatInZone(iso: string, zone: string): string {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: zone,
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(iso));
}

export function groupRulesByWeekday(rules: AvailabilityRule[]): AvailabilityRule[][] {
  const groups: AvailabilityRule[][] = WEEKDAYS.map(() => []);
  for (const rule of rules) groups[rule.weekday]?.push(rule);
  for (const group of groups) group.sort((a, b) => a.start_time.localeCompare(b.start_time));
  return groups;
}

/** API times are `HH:MM:SS`; show `HH:MM`. */
export const shortTime = (value: string) => value.slice(0, 5);
