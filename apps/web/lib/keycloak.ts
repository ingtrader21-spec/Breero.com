const enabled = process.env.NEXT_PUBLIC_KEYCLOAK_ENABLED === "true";
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api/v1").replace(/\/$/, "");

async function csrfToken(): Promise<string> {
  const value = document.cookie.split("; ").find((item) => item.startsWith("breero_csrf="));
  if (value && new URL(apiBase, window.location.href).origin === window.location.origin) {
    return decodeURIComponent(value.split("=")[1] ?? "");
  }
  const response = await fetch(`${apiBase}/auth/csrf`, { credentials: "include", cache: "no-store" });
  if (response.status === 401) return "";
  if (!response.ok) throw new Error("Unable to verify browser session");
  return ((await response.json()) as { csrf_token: string }).csrf_token;
}

export const keycloak = {
  enabled,
  async login(returnTo = "/account") {
    if (!enabled) throw new Error("Keycloak login is unavailable");
    window.location.assign(`${apiBase}/auth/keycloak/login?return_to=${encodeURIComponent(returnTo)}`);
  },
  async logout() {
    const response = await fetch(`${apiBase}/auth/keycloak/logout`, {
      method: "POST",
      credentials: "include",
      headers: { "X-CSRF-Token": await csrfToken() },
    });
    if (!response.ok && response.status !== 401) throw new Error("Logout failed");
    if (response.ok) {
      const body = (await response.json()) as { end_session_url?: string };
      if (body.end_session_url) {
        window.location.assign(body.end_session_url);
        return;
      }
    }
    window.location.assign("/");
  },
};
