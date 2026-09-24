import { createHash, generateKeyPairSync, sign, type KeyObject } from "node:crypto";
import { vi } from "vitest";

import type { PortalRuntimeConfig } from "./types";

export const origin = "http://localhost:3000";
export const issuer = "http://localhost:8080/realms/test";
export const clientId = "portal";
export const apiBase = "http://api/api/v1";

export const adminConfig: PortalRuntimeConfig = {
  kind: "admin",
  title: "Admin",
  eyebrow: "Admin",
  allowedRoles: ["admin"],
  apiRules: [
    { prefix: "/admin", methods: ["GET", "POST"] },
    { prefix: "/portal/admin", methods: ["GET"] },
  ],
};
export const partnerConfig: PortalRuntimeConfig = {
  kind: "partner",
  title: "Partner",
  eyebrow: "Partner",
  allowedRoles: ["vendor_admin"],
  apiRules: [{ prefix: "/portal/provider", methods: ["GET"] }],
};

function keyPair(): { privateKey: KeyObject; jwk: Record<string, unknown> } {
  const { privateKey, publicKey } = generateKeyPairSync("rsa", { modulusLength: 2048 });
  return { privateKey, jwk: publicKey.export({ format: "jwk" }) as Record<string, unknown> };
}

const trusted = keyPair();
const untrusted = keyPair();

export type IdentityProvider = {
  userId: string;
  roles: string[];
  isActive: boolean;
  tokenSerial: number;
  refreshStatus: number;
  apiStatus: number;
  upstreamStatus: number;
  idTokenOverrides: Record<string, unknown>;
  signWithUntrustedKey: boolean;
  lastChallenge: string | null;
  lastNonce: string | null;
  tokenGrants: URLSearchParams[];
  endSessionCalls: URLSearchParams[];
  upstream: Array<{ url: string; method: string; headers: Headers }>;
  fetcher: ReturnType<typeof vi.fn>;
};

function b64(value: unknown): string {
  return Buffer.from(JSON.stringify(value)).toString("base64url");
}

export function idToken(claims: Record<string, unknown>, key: KeyObject = trusted.privateKey, kid = "trusted"): string {
  const head = b64({ alg: "RS256", typ: "JWT", kid });
  const body = b64(claims);
  return `${head}.${body}.${sign("sha256", Buffer.from(`${head}.${body}`), key).toString("base64url")}`;
}

export const trustedJwk = { ...trusted.jwk, kid: "trusted", use: "sig", alg: "RS256" };
export const untrustedPrivateKey = untrusted.privateKey;

export function identityProvider(): IdentityProvider {
  const idp: IdentityProvider = {
    userId: "user-1",
    roles: ["admin"],
    isActive: true,
    tokenSerial: 0,
    refreshStatus: 200,
    apiStatus: 200,
    upstreamStatus: 200,
    idTokenOverrides: {},
    signWithUntrustedKey: false,
    lastChallenge: null,
    lastNonce: null,
    tokenGrants: [],
    endSessionCalls: [],
    upstream: [],
    fetcher: vi.fn(),
  };
  idp.fetcher.mockImplementation(async (input: URL | string, init?: RequestInit) => {
    const url = String(input);
    if (url === `${issuer}/.well-known/openid-configuration`) {
      return Response.json({
        issuer,
        authorization_endpoint: `${issuer}/protocol/openid-connect/auth`,
        token_endpoint: `${issuer}/protocol/openid-connect/token`,
        jwks_uri: `${issuer}/protocol/openid-connect/certs`,
        end_session_endpoint: `${issuer}/protocol/openid-connect/logout`,
      });
    }
    if (url === `${issuer}/protocol/openid-connect/certs`) return Response.json({ keys: [trustedJwk] });
    if (url === `${issuer}/protocol/openid-connect/token`) {
      const body = new URLSearchParams(String(init?.body));
      idp.tokenGrants.push(body);
      if (body.get("grant_type") === "refresh_token" && idp.refreshStatus !== 200) {
        return new Response("{}", { status: idp.refreshStatus });
      }
      if (body.get("grant_type") === "authorization_code") {
        const challenge = createHash("sha256").update(body.get("code_verifier") ?? "").digest("base64url");
        if (challenge !== idp.lastChallenge) return new Response("{}", { status: 400 });
      }
      idp.tokenSerial += 1;
      const now = Math.floor(Date.now() / 1000);
      const claims = { iss: issuer, sub: `kc-${idp.userId}`, aud: clientId, exp: now + 300, iat: now, nonce: idp.lastNonce, ...idp.idTokenOverrides };
      return Response.json({
        access_token: `access-${idp.tokenSerial}`,
        refresh_token: `refresh-${idp.tokenSerial}`,
        id_token: idp.signWithUntrustedKey ? idToken(claims, untrusted.privateKey) : idToken(claims),
        expires_in: 300,
        refresh_expires_in: 1800,
        token_type: "Bearer",
      });
    }
    if (url === `${issuer}/protocol/openid-connect/logout`) {
      idp.endSessionCalls.push(new URLSearchParams(String(init?.body)));
      return new Response(null, { status: 204 });
    }
    if (url.startsWith(apiBase)) {
      const path = url.slice(apiBase.length);
      const user = { id: idp.userId, email: "person@example.test", full_name: "Person", role: idp.roles[0] ?? "customer", is_active: idp.isActive, email_verified: true };
      if (idp.apiStatus !== 200 && ["/auth/me", "/auth/access/me", "/portal/capabilities"].includes(path)) {
        return new Response("{}", { status: idp.apiStatus });
      }
      if (path === "/auth/me") return Response.json(user);
      if (path === "/auth/access/me") return Response.json({ user, roles: idp.roles, permissions: [], assignments: [] });
      if (path === "/portal/capabilities") return Response.json({});
      idp.upstream.push({ url, method: init?.method ?? "GET", headers: new Headers(init?.headers) });
      return Response.json({ ok: idp.upstreamStatus === 200, path }, { status: idp.upstreamStatus });
    }
    throw new Error(`unexpected fetch ${url}`);
  });
  return idp;
}

export function setCookies(response: Response): string[] {
  return response.headers.getSetCookie();
}

export function cookieValue(response: Response, name: string): string | null {
  for (const value of setCookies(response)) {
    const [pair] = value.split(";");
    const index = pair?.indexOf("=") ?? -1;
    if (pair && index > 0 && pair.slice(0, index) === name) return pair.slice(index + 1);
  }
  return null;
}
