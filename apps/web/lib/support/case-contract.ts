/**
 * Truthful provisioning state for the SupportCase API (PAS-127, M20).
 *
 * `apps/api/openapi.json` currently exposes no support-case operations
 * (Notion contract gate DB-12 is open). The workspace therefore renders a
 * degraded "not provisioned" state and never requests or fabricates cases.
 * `case-contract.test.ts` fails as soon as the checked-in OpenAPI gains
 * support-case paths, forcing this flag and the real client wiring to change
 * together.
 */
export type SupportCaseApiState = "unprovisioned" | "available";

export const SUPPORT_CASE_API_STATE: SupportCaseApiState = "unprovisioned";

/** Matches OpenAPI paths that would carry SupportCase operations. */
export const SUPPORT_CASE_PATH_PATTERN = /support[-_/]?cases?\b|\/cases?\//i;
