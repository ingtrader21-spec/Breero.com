import type { PostalCodeImportRow } from "./types";

const ZIP_RE = /^[0-9]{5}(?:-[0-9]{4})?$/;
const STATE_RE = /^[A-Z]{2,3}$/;
export const MAX_IMPORT_ROWS = 5000;

export function normalizePostalCode(value: string): string | null {
  let normalized = value.trim();
  if (/^[0-9]{9}$/.test(normalized)) normalized = `${normalized.slice(0, 5)}-${normalized.slice(5)}`;
  return ZIP_RE.test(normalized) ? normalized : null;
}

export function parsePostalCodeList(text: string): { codes: string[]; invalid: string[] } {
  const codes: string[] = [];
  const invalid: string[] = [];
  for (const token of text.split(/[\s,;]+/).filter(Boolean)) {
    const normalized = normalizePostalCode(token);
    if (normalized) { if (!codes.includes(normalized)) codes.push(normalized); }
    else invalid.push(token);
  }
  return { codes, invalid };
}

function parseBool(value: string | undefined, fallback: boolean): boolean | null {
  if (value === undefined || value.trim() === "") return fallback;
  const lowered = value.trim().toLowerCase();
  if (["true", "yes", "1", "y"].includes(lowered)) return true;
  if (["false", "no", "0", "n"].includes(lowered)) return false;
  return null;
}

export interface ImportParseResult { rows: PostalCodeImportRow[]; errors: string[] }

/**
 * Parses CSV with header `postal_code[,city,state_code,active,regular_service_enabled,
 * emergency_service_enabled,priority]`. Validation mirrors the API so a bad file is
 * rejected locally before any Idempotency-Key is spent.
 */
export function parsePostalCodeCsv(text: string): ImportParseResult {
  const lines = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const errors: string[] = [];
  if (lines.length === 0) return { rows: [], errors: ["The file is empty."] };
  const header = lines[0].split(",").map((cell) => cell.trim().toLowerCase());
  if (!header.includes("postal_code")) return { rows: [], errors: ["Header must include postal_code."] };
  const known = new Set(["postal_code", "city", "state_code", "active", "regular_service_enabled", "emergency_service_enabled", "priority"]);
  const unknown = header.filter((column) => !known.has(column));
  if (unknown.length) errors.push(`Unknown columns: ${unknown.join(", ")}.`);
  const rows: PostalCodeImportRow[] = [];
  const seen = new Set<string>();
  lines.slice(1).forEach((line, index) => {
    const lineNo = index + 2;
    const cells = line.split(",").map((cell) => cell.trim());
    const record = Object.fromEntries(header.map((column, i) => [column, cells[i] ?? ""]));
    const postal = normalizePostalCode(record.postal_code ?? "");
    if (!postal) { errors.push(`Line ${lineNo}: invalid postal code "${record.postal_code ?? ""}".`); return; }
    if (seen.has(postal)) { errors.push(`Line ${lineNo}: duplicate postal code ${postal}.`); return; }
    seen.add(postal);
    const state = record.state_code ? record.state_code.toUpperCase() : null;
    if (state && !STATE_RE.test(state)) { errors.push(`Line ${lineNo}: invalid state code "${record.state_code}".`); return; }
    const active = parseBool(record.active, true);
    const regular = parseBool(record.regular_service_enabled, true);
    const emergency = parseBool(record.emergency_service_enabled, false);
    if (active === null || regular === null || emergency === null) { errors.push(`Line ${lineNo}: boolean columns must be true/false.`); return; }
    let priority = 100;
    if (record.priority) {
      priority = Number(record.priority);
      if (!Number.isInteger(priority) || priority < 0 || priority > 10000) { errors.push(`Line ${lineNo}: priority must be 0–10000.`); return; }
    }
    rows.push({
      postal_code: postal,
      city: record.city ? record.city.slice(0, 120) : null,
      state_code: state,
      active,
      regular_service_enabled: regular,
      emergency_service_enabled: emergency,
      priority,
    });
  });
  if (rows.length > MAX_IMPORT_ROWS) errors.push(`At most ${MAX_IMPORT_ROWS} rows can be imported at once.`);
  if (rows.length === 0 && errors.length === 0) errors.push("No data rows were found.");
  return { rows, errors };
}

export interface ZoneFormValues {
  legal_entity_id: string;
  name: string;
  state_code: string;
  city: string;
  postal_codes: string;
  priority: string;
  regular_service_enabled: boolean;
  emergency_enabled: boolean;
}

/** Builds a create payload; only non-geometric selectors are editable in the admin UI. */
export function buildZoneCreatePayload(values: ZoneFormValues): { payload: Record<string, unknown> | null; errors: string[] } {
  const errors: string[] = [];
  if (!/^[0-9a-f-]{36}$/i.test(values.legal_entity_id.trim())) errors.push("Legal entity ID must be a UUID.");
  if (!values.name.trim()) errors.push("Name is required.");
  const state = values.state_code.trim().toUpperCase();
  if (state && !STATE_RE.test(state)) errors.push("State code must be 2–3 letters.");
  const { codes, invalid } = parsePostalCodeList(values.postal_codes);
  if (invalid.length) errors.push(`Invalid postal codes: ${invalid.join(", ")}.`);
  const priority = values.priority.trim() ? Number(values.priority) : 100;
  if (!Number.isInteger(priority) || priority < 0 || priority > 10000) errors.push("Priority must be 0–10000.");
  if (!codes.length && !values.city.trim() && !state) errors.push("Choose at least one coverage selector: postal codes, city or state.");
  if (errors.length) return { payload: null, errors };
  return {
    payload: {
      legal_entity_id: values.legal_entity_id.trim(),
      name: values.name.trim(),
      country_code: "US",
      state_code: state || null,
      city: values.city.trim() || null,
      postal_codes: codes,
      priority,
      regular_service_enabled: values.regular_service_enabled,
      emergency_enabled: values.emergency_enabled,
      active: true,
    },
    errors,
  };
}

/**
 * The admin intentionally renders no map. Zone centers and boundaries are operator
 * configuration, but a tile map would send coverage coordinates to a third-party
 * tile host; we only show a coarse, non-precise description instead.
 */
export function describeCoverage(zone: { center: { latitude: number; longitude: number } | null; radius_miles: number | null; boundary_configured: boolean; postal_codes: string[]; city: string | null; state_code: string | null }): string[] {
  const parts: string[] = [];
  if (zone.postal_codes.length) parts.push(`${zone.postal_codes.length} postal code${zone.postal_codes.length === 1 ? "" : "s"}`);
  if (zone.city) parts.push(`City: ${zone.city}`);
  if (zone.state_code) parts.push(`State: ${zone.state_code}`);
  if (zone.center && zone.radius_miles) parts.push(`Radius coverage: ${zone.radius_miles} mi around a configured center`);
  if (zone.boundary_configured) parts.push("Custom boundary configured");
  return parts.length ? parts : ["No coverage selector configured"];
}
