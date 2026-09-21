import {
  createCipheriv,
  createDecipheriv,
  createHash,
  randomBytes,
  timingSafeEqual,
} from "node:crypto";
import { readFileSync } from "node:fs";

import type {
  PortalCapabilities,
  PortalContext,
  PortalHttpMethod,
  PortalProblem,
  PortalRuntimeConfig,
  PortalSessionView,
  PortalUser,
} from "./types";

const VERSION = 1;
const COOKIE_LIMIT = 3800;
const MAX_BODY = 1_048_576;
const TIMEOUT_MS = 12_000;
const AAD = Buffer.from("breero-portal:v1");
const NAMES = {
  access: "breero-portal-access",
  refresh: "breero-portal-refresh",
  profile: "breero-portal-profile",
  oidc: "breero-portal-oidc",
};

type Environment = {
  production: boolean;
  origin: URL;
  issuer: URL;
  clientId: string;
  clientSecret: string | null;
  apiBase: URL;
  key: Buffer;
};
type Discovery = {
  issuer: string;
  authorization_endpoint: string;
  token_endpoint: string;
  end_session_endpoint?: string;
};
type Tokens = {
  access_token: string;
  refresh_token?: string;
  id_token?: string;
  expires_in: number;
  refresh_expires_in?: number;
  token_type: string;
};
type Access = { v: number; token: string; expiresAt: number };
type Refresh = { v: number; token: string; expiresAt: number };
type ProfileCookie = { v: number; csrfToken: string };

type Profile = {
  v: number;
  user: PortalUser;
  context: PortalContext;
  capabilities: PortalCapabilities;
  csrfToken: string;
  issuedAt: number;
};
type OidcState = {
  v: number;
  state: string;
  nonce: string;
  verifier: string;
  returnTo: string;
  createdAt: number;
};
type Session = { access: Access; refresh: Refresh; profile: Profile; changed: boolean };

let discoveryCache: { issuer: string; expiresAt: number; value: Discovery } | null = null;
const now = () => Math.floor(Date.now() / 1000);
const random = (bytes = 32) => randomBytes(bytes).toString("base64url");

function required(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`${name} is required`);
  return value;
}

function secret(pathName: string, developmentName?: string): string {
  const path = process.env[pathName]?.trim();
  if (path) {
    const value = readFileSync(path, "utf8").trim();
    if (!value) throw new Error(`${pathName} points to an empty secret`);
    return value;
  }
  if (developmentName && process.env.NODE_ENV !== "production") {
    const value = process.env[developmentName]?.trim();
    if (value) return value;
  }
  throw new Error(`${pathName} is required`);
}

function parsedUrl(name: string, value: string, requireHttps: boolean): URL {
  const url = new URL(value);
  if (url.username || url.password || url.hash) throw new Error(`${name} is invalid`);
  if (requireHttps && url.protocol !== "https:") throw new Error(`${name} must use HTTPS`);
  if (!["http:", "https:"].includes(url.protocol)) throw new Error(`${name} must use HTTP(S)`);
  return url;
}

function environment(): Environment {
  const production = process.env.NODE_ENV === "production";
  const origin = parsedUrl("PORTAL_PUBLIC_ORIGIN", required("PORTAL_PUBLIC_ORIGIN"), production);
  if (origin.pathname !== "/" || origin.search) throw new Error("PORTAL_PUBLIC_ORIGIN must be an origin");
  const issuer = parsedUrl("KEYCLOAK_ISSUER", required("KEYCLOAK_ISSUER"), production);
  issuer.pathname = issuer.pathname.replace(/\/$/, "");
  const apiBase = parsedUrl("BREERO_API_INTERNAL_URL", required("BREERO_API_INTERNAL_URL"), false);
  apiBase.pathname = apiBase.pathname.replace(/\/$/, "");
  const privateHost =
    ["api", "localhost", "127.0.0.1"].includes(apiBase.hostname) ||
    apiBase.hostname.endsWith(".internal") ||
    apiBase.hostname.endsWith(".local") ||
    /^10\./.test(apiBase.hostname) ||
    /^192\.168\./.test(apiBase.hostname) ||
    /^172\.(1[6-9]|2\d|3[01])\./.test(apiBase.hostname);
  if (production && apiBase.protocol !== "https:" && !privateHost) {
    throw new Error("BREERO_API_INTERNAL_URL must be HTTPS or private");
  }
  const sessionSecret = secret("PORTAL_SESSION_SECRET_FILE", "PORTAL_SESSION_SECRET");
  if (sessionSecret.length < 32) throw new Error("Portal session secret must be at least 32 characters");
  const clientSecretPath = process.env.KEYCLOAK_CLIENT_SECRET_FILE?.trim();
  const clientSecret = clientSecretPath
    ? readFileSync(clientSecretPath, "utf8").trim() || null
    : production
      ? null
      : process.env.KEYCLOAK_CLIENT_SECRET?.trim() || null;
  return {
    production,
    origin,
    issuer,
    clientId: required("KEYCLOAK_CLIENT_ID"),
    clientSecret,
    apiBase,
    key: createHash("sha256").update(sessionSecret).digest(),
  };
}

function seal(value: unknown, key: Buffer): string {
  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", key, iv);
  cipher.setAAD(AAD);
  const encrypted = Buffer.concat([cipher.update(JSON.stringify(value), "utf8"), cipher.final()]);
  const result = `v1.${iv.toString("base64url")}.${cipher.getAuthTag().toString("base64url")}.${encrypted.toString("base64url")}`;
  if (result.length > COOKIE_LIMIT) throw new Error("Portal session envelope is too large");
  return result;
}

function unseal<T>(value: string | undefined, key: Buffer): T | null {
  if (!value || value.length > COOKIE_LIMIT) return null;
  try {
    const [version, ivValue, tagValue, encryptedValue, ...extra] = value.split(".");
    if (version !== "v1" || !ivValue || !tagValue || !encryptedValue || extra.length) return null;
    const iv = Buffer.from(ivValue, "base64url");
    const tag = Buffer.from(tagValue, "base64url");
    const encrypted = Buffer.from(encryptedValue, "base64url");
    if (iv.length !== 12 || tag.length !== 16 || !encrypted.length) return null;
    const decipher = createDecipheriv("aes-256-gcm", key, iv);
    decipher.setAAD(AAD);
    decipher.setAuthTag(tag);
    return JSON.parse(Buffer.concat([decipher.update(encrypted), decipher.final()]).toString("utf8")) as T;
  } catch {
    return null;
  }
}

function names(env: Environment) {
  const prefix = env.production ? "__Host-" : "";
  return Object.fromEntries(Object.entries(NAMES).map(([key, value]) => [key, `${prefix}${value}`])) as typeof NAMES;
}

function cookies(request: Request): Map<string, string> {
  const result = new Map<string, string>();
  for (const part of (request.headers.get("cookie") ?? "").split(";")) {
    const index = part.indexOf("=");
    if (index > 0) result.set(part.slice(0, index).trim(), part.slice(index + 1).trim());
  }
  return result;
}

function serialized(name: string, value: string, maxAge: number, secure: boolean): string {
  const attributes = [
    `${name}=${value}`,
    "Path=/",
    `Max-Age=${Math.max(0, Math.floor(maxAge))}`,
    "HttpOnly",
    "SameSite=Lax",
    "Priority=High",
  ];
  if (secure) attributes.push("Secure");
  return attributes.join("; ");
}

function setCookie(headers: Headers, value: string): void {
  headers.append("Set-Cookie", value);
}

function clearCookies(headers: Headers, env: Environment): void {
  for (const name of Object.values(names(env))) setCookie(headers, serialized(name, "", 0, env.production));
}

function writeSession(headers: Headers, env: Environment, session: Session): void {
  const cookieNames = names(env);
  setCookie(headers, serialized(cookieNames.access, seal(session.access, env.key), session.access.expiresAt - now(), env.production));
  setCookie(headers, serialized(cookieNames.refresh, seal(session.refresh, env.key), session.refresh.expiresAt - now(), env.production));
  setCookie(headers, serialized(cookieNames.profile, seal({ v: VERSION, csrfToken: session.profile.csrfToken }, env.key), session.refresh.expiresAt - now(), env.production));
}

function equal(left: string, right: string): boolean {
  const a = Buffer.from(left);
  const b = Buffer.from(right);
  return a.length === b.length && timingSafeEqual(a, b);
}

export function safeReturnTo(value: string | null | undefined): string {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return "/";
  try {
    const decoded = decodeURIComponent(value);
    return decoded.includes("\\") || decoded.startsWith("//") ? "/" : value;
  } catch {
    return "/";
  }
}

function json(value: unknown, status = 200, headers = new Headers()): Response {
  headers.set("Content-Type", "application/json; charset=utf-8");
  headers.set("Cache-Control", "no-store, max-age=0");
  return new Response(JSON.stringify(value), { status, headers });
}

function problem(status: number, message: string, requestId?: string, code?: string, headers = new Headers()): Response {
  const body: PortalProblem = { status, message, requestId, code };
  return json(body, status, headers);
}

function redirect(location: string, headers = new Headers()): Response {
  headers.set("Location", location);
  headers.set("Cache-Control", "no-store");
  return new Response(null, { status: 303, headers });
}

async function discovery(env: Environment): Promise<Discovery> {
  if (discoveryCache?.issuer === env.issuer.toString() && discoveryCache.expiresAt > now()) {
    return discoveryCache.value;
  }
  const endpoint = new URL(`${env.issuer.toString()}/.well-known/openid-configuration`);
  const response = await fetch(endpoint, { cache: "no-store", signal: AbortSignal.timeout(TIMEOUT_MS) });
  if (!response.ok) throw new Error("OIDC discovery failed");
  const value = (await response.json()) as Discovery;
  if (value.issuer.replace(/\/$/, "") !== env.issuer.toString()) throw new Error("OIDC issuer mismatch");
  for (const field of [value.authorization_endpoint, value.token_endpoint]) {
    if (new URL(field).origin !== env.issuer.origin) throw new Error("OIDC endpoint origin mismatch");
  }
  discoveryCache = { issuer: env.issuer.toString(), expiresAt: now() + 300, value };
  return value;
}

async function tokenRequest(env: Environment, parameters: URLSearchParams): Promise<Tokens> {
  const oidc = await discovery(env);
  parameters.set("client_id", env.clientId);
  if (env.clientSecret) parameters.set("client_secret", env.clientSecret);
  const response = await fetch(oidc.token_endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded", Accept: "application/json" },
    body: parameters,
    cache: "no-store",
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  if (!response.ok) throw new Error("OIDC token exchange failed");
  const tokens = (await response.json()) as Tokens;
  if (!tokens.access_token || !tokens.expires_in || tokens.token_type.toLowerCase() !== "bearer") {
    throw new Error("OIDC token response is invalid");
  }
  return tokens;
}

function jwtNonce(token: string): string | null {
  try {
    const payload = JSON.parse(Buffer.from(token.split(".")[1] ?? "", "base64url").toString("utf8")) as { nonce?: unknown };
    return typeof payload.nonce === "string" ? payload.nonce : null;
  } catch {
    return null;
  }
}

async function apiJson<T>(env: Environment, token: string, path: string): Promise<T> {
  const response = await fetch(new URL(`${env.apiBase.toString()}${path}`), {
    headers: { Accept: "application/json", Authorization: `Bearer ${token}` },
    cache: "no-store",
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  if (!response.ok) throw new Error(`BREERO API rejected ${path}`);
  return (await response.json()) as T;
}

async function loadProfile(env: Environment, token: string): Promise<Profile> {
  const [user, context, capabilities] = await Promise.all([
    apiJson<PortalUser>(env, token, "/auth/me"),
    apiJson<PortalContext>(env, token, "/auth/access/me"),
    apiJson<PortalCapabilities>(env, token, "/portal/capabilities"),
  ]);
  return { v: VERSION, user, context, capabilities, csrfToken: random(), issuedAt: now() };
}

function authorize(profile: Profile, config: PortalRuntimeConfig): void {
  if (!profile.user.is_active || !profile.user.email_verified) throw new Error("Account is inactive or unverified");
  if (!profile.context.roles.some((role) => config.allowedRoles.includes(role))) throw new Error("Portal role is not assigned");
}

function buildSession(tokens: Tokens, profile: Profile): Session {
  const issued = now();
  const refreshLifetime = Math.max(tokens.refresh_expires_in ?? 1800, tokens.expires_in);
  return {
    access: { v: VERSION, token: tokens.access_token, expiresAt: issued + tokens.expires_in },
    refresh: { v: VERSION, token: tokens.refresh_token ?? "", expiresAt: issued + refreshLifetime },
    profile,
    changed: true,
  };
}

async function currentSession(request: Request, env: Environment, config: PortalRuntimeConfig): Promise<Session | null> {
  const values = cookies(request);
  const cookieNames = names(env);
  let access = unseal<Access>(values.get(cookieNames.access), env.key);
  let refresh = unseal<Refresh>(values.get(cookieNames.refresh), env.key);
  const stored = unseal<ProfileCookie>(values.get(cookieNames.profile), env.key);
  if (access?.v !== VERSION || refresh?.v !== VERSION || stored?.v !== VERSION || !stored.csrfToken || refresh.expiresAt <= now()) return null;
  let changed = false;
  let profile: Profile | undefined;
  if (access.expiresAt <= now() + 60) {
    if (!refresh.token) return null;
    const tokens = await tokenRequest(env, new URLSearchParams({ grant_type: "refresh_token", refresh_token: refresh.token }));
    profile = await loadProfile(env, tokens.access_token);
    const renewed = buildSession(tokens, profile);
    access = renewed.access;
    refresh = tokens.refresh_token ? renewed.refresh : refresh;
    changed = true;
  }
  // Access assignments remain authoritative API data, not oversized cookie data.
  profile ??= await loadProfile(env, access.token);
  profile.csrfToken = stored.csrfToken;
  authorize(profile, config);
  return { access, refresh, profile, changed };
}

function sessionView(session: Session): PortalSessionView {
  return {
    user: session.profile.user,
    context: session.profile.context,
    capabilities: session.profile.capabilities,
    csrf_token: session.profile.csrfToken,
    expires_at: session.access.expiresAt,
  };
}

function sameOrigin(request: Request, env: Environment): boolean {
  const origin = request.headers.get("origin");
  return Boolean(origin && origin === env.origin.origin);
}

async function beginLogin(request: Request, config: PortalRuntimeConfig): Promise<Response> {
  const env = environment();
  const oidc = await discovery(env);
  const state: OidcState = {
    v: VERSION,
    state: random(),
    nonce: random(),
    verifier: random(48),
    returnTo: safeReturnTo(new URL(request.url).searchParams.get("return_to") ?? config.homePath),
    createdAt: now(),
  };
  const endpoint = new URL(oidc.authorization_endpoint);
  endpoint.searchParams.set("client_id", env.clientId);
  endpoint.searchParams.set("redirect_uri", new URL("/api/auth/callback", env.origin).toString());
  endpoint.searchParams.set("response_type", "code");
  endpoint.searchParams.set("scope", "openid profile email");
  endpoint.searchParams.set("state", state.state);
  endpoint.searchParams.set("nonce", state.nonce);
  endpoint.searchParams.set("code_challenge_method", "S256");
  endpoint.searchParams.set("code_challenge", createHash("sha256").update(state.verifier).digest("base64url"));
  const headers = new Headers();
  const cookieName = names(env).oidc;
  setCookie(headers, serialized(cookieName, seal(state, env.key), 600, env.production));
  return redirect(endpoint.toString(), headers);
}

async function callback(request: Request, config: PortalRuntimeConfig): Promise<Response> {
  const env = environment();
  const url = new URL(request.url);
  const headers = new Headers();
  const cookieName = names(env).oidc;
  const stored = unseal<OidcState>(cookies(request).get(cookieName), env.key);
  setCookie(headers, serialized(cookieName, "", 0, env.production));
  const code = url.searchParams.get("code");
  const state = url.searchParams.get("state");
  if (url.searchParams.get("error") || !code || !state || stored?.v !== VERSION || stored.createdAt < now() - 600 || !equal(state, stored.state)) {
    return redirect(`/login?error=${encodeURIComponent("Sign-in state expired")}`, headers);
  }
  try {
    const tokens = await tokenRequest(env, new URLSearchParams({
      grant_type: "authorization_code",
      code,
      redirect_uri: new URL("/api/auth/callback", env.origin).toString(),
      code_verifier: stored.verifier,
    }));
    if (!tokens.id_token || jwtNonce(tokens.id_token) !== stored.nonce) throw new Error("OIDC nonce validation failed");
    const session = buildSession(tokens, await loadProfile(env, tokens.access_token));
    authorize(session.profile, config);
    writeSession(headers, env, session);
    return redirect(stored.returnTo || config.homePath || "/", headers);
  } catch (error) {
    console.error("portal_login_failed", { portal: config.kind, reason: error instanceof Error ? error.message : "unknown" });
    clearCookies(headers, env);
    return redirect(`/login?error=${encodeURIComponent("Account is not authorized")}`, headers);
  }
}

async function getSession(request: Request, config: PortalRuntimeConfig): Promise<Response> {
  const env = environment();
  const headers = new Headers();
  const session = await currentSession(request, env, config);
  if (!session) {
    clearCookies(headers, env);
    return problem(401, "Authentication required", undefined, "SESSION_REQUIRED", headers);
  }
  if (session.changed) writeSession(headers, env, session);
  return json(sessionView(session), 200, headers);
}

async function logout(request: Request): Promise<Response> {
  const env = environment();
  const headers = new Headers();
  const profile = unseal<ProfileCookie>(cookies(request).get(names(env).profile), env.key);
  if (!sameOrigin(request, env)) return problem(403, "Invalid request origin", undefined, "INVALID_ORIGIN", headers);
  if (profile?.v !== VERSION || !equal(request.headers.get("x-csrf-token") ?? "", profile.csrfToken)) {
    clearCookies(headers, env);
    return problem(403, "Invalid CSRF token", undefined, "INVALID_CSRF", headers);
  }
  clearCookies(headers, env);
  let logoutUrl = new URL("/login", env.origin).toString();
  try {
    const oidc = await discovery(env);
    if (oidc.end_session_endpoint) {
      const endpoint = new URL(oidc.end_session_endpoint);
      endpoint.searchParams.set("client_id", env.clientId);
      endpoint.searchParams.set("post_logout_redirect_uri", logoutUrl);
      logoutUrl = endpoint.toString();
    }
  } catch {
    // Local session destruction remains authoritative.
  }
  return json({ logout_url: logoutUrl }, 200, headers);
}

export async function handlePortalAuthGet(request: Request, action: string, config: PortalRuntimeConfig): Promise<Response> {
  try {
    if (action === "login") return await beginLogin(request, config);
    if (action === "callback") return await callback(request, config);
    if (action === "session") return await getSession(request, config);
    return problem(405, "Method not allowed", undefined, "METHOD_NOT_ALLOWED");
  } catch (error) {
    console.error("portal_auth_unavailable", { portal: config.kind, action, reason: error instanceof Error ? error.message : "unknown" });
    return problem(503, "Portal authentication is unavailable", undefined, "AUTH_UNAVAILABLE");
  }
}

export async function handlePortalAuthPost(request: Request, action: string, config: PortalRuntimeConfig): Promise<Response> {
  try {
    return action === "logout" ? await logout(request) : problem(405, "Method not allowed", undefined, "METHOD_NOT_ALLOWED");
  } catch (error) {
    console.error("portal_auth_unavailable", { portal: config.kind, action, reason: error instanceof Error ? error.message : "unknown" });
    return problem(503, "Portal authentication is unavailable", undefined, "AUTH_UNAVAILABLE");
  }
}

function apiPath(parts: readonly string[]): string | null {
  if (!parts.length || parts.length > 12) return null;
  const decoded: string[] = [];
  for (const raw of parts) {
    try {
      const value = decodeURIComponent(raw);
      if (!value || [".", ".."].includes(value) || value.includes("/") || value.includes("\\")) return null;
      decoded.push(value);
    } catch {
      return null;
    }
  }
  return `/${decoded.join("/")}`;
}

export function isAllowedPortalRequest(path: string, method: string, config: PortalRuntimeConfig): boolean {
  const normalized = method.toUpperCase() as PortalHttpMethod;
  return config.apiRules.some((rule) => (path === rule.prefix || path.startsWith(`${rule.prefix}/`)) && rule.methods.includes(normalized));
}

function correlationId(request: Request): string {
  const value = request.headers.get("x-correlation-id")?.trim();
  return value && /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(value) ? value : random(18);
}

class BodyReadError extends Error {
  constructor(readonly status: number) { super("Request body limit exceeded"); }
}

export async function readLimitedBody(request: Request, maxBytes = MAX_BODY, timeoutMs = TIMEOUT_MS): Promise<ArrayBuffer> {
  if (!request.body) return new ArrayBuffer(0);
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const deadline = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new BodyReadError(408)), timeoutMs);
  });
  try {
    while (true) {
      const { done, value } = await Promise.race([reader.read(), deadline]);
      if (done) break;
      size += value.byteLength;
      if (size > maxBytes) throw new BodyReadError(413);
      chunks.push(value);
    }
    const result = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) { result.set(chunk, offset); offset += chunk.byteLength; }
    return result.buffer;
  } catch (error) {
    void reader.cancel().catch(() => undefined);
    throw error;
  } finally {
    clearTimeout(timer);
    reader.releaseLock();
  }
}

export async function proxyPortalApi(request: Request, pathParts: readonly string[], config: PortalRuntimeConfig): Promise<Response> {
  const requestId = correlationId(request);
  let env: Environment;
  try {
    env = environment();
  } catch (error) {
    console.error("portal_runtime_invalid", { portal: config.kind, reason: error instanceof Error ? error.message : "unknown" });
    return problem(503, "Portal service is unavailable", requestId, "RUNTIME_INVALID");
  }
  const headers = new Headers();
  const session = await currentSession(request, env, config);
  if (!session) {
    clearCookies(headers, env);
    return problem(401, "Authentication required", requestId, "SESSION_REQUIRED", headers);
  }
  const path = apiPath(pathParts);
  if (!path || !isAllowedPortalRequest(path, request.method, config)) {
    return problem(403, "Portal operation is not allowed", requestId, "OPERATION_DENIED");
  }
  const method = request.method.toUpperCase();
  const mutation = !["GET", "HEAD", "OPTIONS"].includes(method);
  if (mutation && (!sameOrigin(request, env) || !equal(request.headers.get("x-csrf-token") ?? "", session.profile.csrfToken))) {
    return problem(403, "Invalid request origin or CSRF token", requestId, "INVALID_CSRF");
  }
  const announcedLength = Number(request.headers.get("content-length") ?? 0);
  if (Number.isFinite(announcedLength) && announcedLength > MAX_BODY) return problem(413, "Request body is too large", requestId, "BODY_TOO_LARGE");
  let body: ArrayBuffer | undefined;
  if (mutation && method !== "DELETE") {
    try {
      body = await readLimitedBody(request);
    } catch (error) {
      const status = error instanceof BodyReadError ? error.status : 400;
      return problem(status, status === 413 ? "Request body is too large" : "Request body could not be read", requestId, "INVALID_BODY");
    }
  }
  const upstreamHeaders = new Headers({
    Accept: "application/json",
    Authorization: `Bearer ${session.access.token}`,
    "X-Correlation-ID": requestId,
  });
  for (const name of ["content-type", "if-match", "idempotency-key"]) {
    const value = request.headers.get(name);
    if (value) upstreamHeaders.set(name, value);
  }
  const input = new URL(request.url);
  const target = new URL(`${env.apiBase.toString()}${path}`);
  target.search = input.search;
  try {
    const upstream = await fetch(target, {
      method,
      headers: upstreamHeaders,
      body,
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    headers.set("Cache-Control", "no-store, max-age=0");
    headers.set("X-Correlation-ID", requestId);
    for (const name of ["content-type", "etag", "x-request-id", "x-correlation-id"]) {
      const value = upstream.headers.get(name);
      if (value) headers.set(name, value);
    }
    if (session.changed) writeSession(headers, env, session);
    if (upstream.status === 401) clearCookies(headers, env);
    return new Response(upstream.body, { status: upstream.status, headers });
  } catch (error) {
    console.error("portal_api_proxy_failed", { portal: config.kind, path, method, correlation_id: requestId, reason: error instanceof Error ? error.name : "unknown" });
    return problem(504, "BREERO API request timed out", requestId, "UPSTREAM_TIMEOUT");
  }
}
