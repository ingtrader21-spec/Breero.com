import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { SUPPORT_CASE_API_STATE, SUPPORT_CASE_PATH_PATTERN } from "./case-contract";

// Vitest runs from apps/web (see vitest.config.ts).
const openapiPath = resolve(process.cwd(), "../api/openapi.json");
const openapi = JSON.parse(readFileSync(openapiPath, "utf8")) as { paths: Record<string, unknown> };

describe("support case contract state", () => {
  it("matches the checked-in OpenAPI contract", () => {
    const supportCasePaths = Object.keys(openapi.paths).filter((path) => SUPPORT_CASE_PATH_PATTERN.test(path));
    expect(SUPPORT_CASE_API_STATE === "available").toBe(supportCasePaths.length > 0);
  });

  it("recognises likely support-case paths", () => {
    expect(SUPPORT_CASE_PATH_PATTERN.test("/api/v1/support/cases")).toBe(true);
    expect(SUPPORT_CASE_PATH_PATTERN.test("/api/v1/support-cases/{case_id}")).toBe(true);
    expect(SUPPORT_CASE_PATH_PATTERN.test("/api/v1/admin/cases/{case_id}/notes")).toBe(true);
    expect(SUPPORT_CASE_PATH_PATTERN.test("/api/v1/admin/audit-events")).toBe(false);
  });
});
