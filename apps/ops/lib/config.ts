const LOCAL_ORIGIN = /^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?(\/|$)/;

/** Resolve the API base (…/api/v1). HTTPS only, except a local API outside production. */
export function resolveApiBase(env: { NEXT_PUBLIC_API_BASE_URL?: string; NODE_ENV?: string }): string {
  const value = env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!value) throw new Error("NEXT_PUBLIC_API_BASE_URL is required");
  const secure = /^https:\/\//.test(value);
  const localDevelopment = env.NODE_ENV !== "production" && LOCAL_ORIGIN.test(value);
  if (!secure && !localDevelopment) throw new Error("A secure API origin is required");
  return value.replace(/\/$/, "");
}

export const OPS_ROLES = ["operations", "admin"] as const;
export const SESSION_KEY = "breero-ops-session";
