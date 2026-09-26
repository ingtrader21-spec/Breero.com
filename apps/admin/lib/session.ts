// Shares the session key used by @breero/portal so a sign-in carries across portals.
export const SESSION_KEY = "breero-portal-session";
export const ADMIN_PORTAL_ROLES = ["admin", "finance"] as const;

export interface AdminSession {
  access_token: string;
  user: { id?: string; email: string; full_name: string; role: string };
}

export function parseSession(raw: string | null): AdminSession | null {
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as Partial<AdminSession>;
    if (typeof value.access_token !== "string" || !value.user || typeof value.user.email !== "string") return null;
    return value as AdminSession;
  } catch {
    return null;
  }
}

export function canUseAdminPortal(session: AdminSession): boolean {
  return (ADMIN_PORTAL_ROLES as readonly string[]).includes(session.user.role);
}
