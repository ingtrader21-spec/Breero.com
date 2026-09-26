import type { Session } from "./types";

// Same key as the shared portal shell so an existing sign-in carries over.
export const SESSION_KEY = "breero-portal-session";
export const PARTNER_ROLES = ["vendor_admin"];

interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export function isPartnerSession(value: unknown): value is Session {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<Session>;
  return (
    typeof candidate.access_token === "string" &&
    candidate.access_token.length > 0 &&
    !!candidate.user &&
    typeof candidate.user.email === "string" &&
    PARTNER_ROLES.includes(candidate.user.role)
  );
}

export function readSession(storage: StorageLike): Session | null {
  const raw = storage.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (isPartnerSession(parsed)) return parsed;
  } catch {
    // fall through and clear the unusable value
  }
  storage.removeItem(SESSION_KEY);
  return null;
}

export function writeSession(storage: StorageLike, session: Session): void {
  storage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function clearSession(storage: StorageLike): void {
  storage.removeItem(SESSION_KEY);
}
