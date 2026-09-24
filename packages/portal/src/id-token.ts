import { createPublicKey, verify, type JsonWebKey } from "node:crypto";

export interface IdTokenClaims {
  iss: string;
  sub: string;
  aud: string | string[];
  exp: number;
  iat: number;
  nonce?: string;
  azp?: string;
  [claim: string]: unknown;
}

export interface IdTokenExpectation {
  issuer: string;
  clientId: string;
  nonce: string;
  now: number;
  skewSeconds?: number;
}

type Jwk = JsonWebKey & { kid?: string; use?: string; alg?: string };
type Header = { alg?: unknown; kid?: unknown; typ?: unknown; crit?: unknown };

const ALGORITHMS: Record<string, { hash: string; kty: string; dsaEncoding?: "ieee-p1363" }> = {
  RS256: { hash: "sha256", kty: "RSA" },
  ES256: { hash: "sha256", kty: "EC", dsaEncoding: "ieee-p1363" },
};

export class IdTokenError extends Error {}

function decodeSegment<T>(segment: string | undefined): T {
  if (!segment) throw new IdTokenError("ID token is malformed");
  try {
    return JSON.parse(Buffer.from(segment, "base64url").toString("utf8")) as T;
  } catch {
    throw new IdTokenError("ID token is malformed");
  }
}

/**
 * Verifies an OIDC ID token signature against the issuer JWKS and validates the
 * issuer, audience, authorized party, lifetime and nonce. Any deviation fails closed.
 */
export function verifyIdToken(token: string, keys: readonly Jwk[], expected: IdTokenExpectation): IdTokenClaims {
  const parts = token.split(".");
  if (parts.length !== 3) throw new IdTokenError("ID token is malformed");
  const [headerSegment, payloadSegment, signatureSegment] = parts as [string, string, string];
  const header = decodeSegment<Header>(headerSegment);
  const algorithm = typeof header.alg === "string" ? ALGORITHMS[header.alg] : undefined;
  if (!algorithm || header.crit !== undefined) throw new IdTokenError("ID token algorithm is not allowed");
  const candidates = keys.filter(
    (key) =>
      key.kty === algorithm.kty &&
      (key.use === undefined || key.use === "sig") &&
      (key.alg === undefined || key.alg === header.alg) &&
      (typeof header.kid !== "string" || key.kid === header.kid),
  );
  if (candidates.length !== 1) throw new IdTokenError("ID token signing key is unknown");
  const signature = Buffer.from(signatureSegment, "base64url");
  let valid = false;
  try {
    const key = createPublicKey({ key: candidates[0] as JsonWebKey, format: "jwk" });
    valid = verify(
      algorithm.hash,
      Buffer.from(`${headerSegment}.${payloadSegment}`),
      algorithm.dsaEncoding ? { key, dsaEncoding: algorithm.dsaEncoding } : key,
      signature,
    );
  } catch {
    valid = false;
  }
  if (!valid) throw new IdTokenError("ID token signature is invalid");

  const claims = decodeSegment<IdTokenClaims>(payloadSegment);
  const skew = expected.skewSeconds ?? 60;
  const audiences = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
  if (typeof claims.iss !== "string" || claims.iss.replace(/\/$/, "") !== expected.issuer.replace(/\/$/, "")) {
    throw new IdTokenError("ID token issuer is invalid");
  }
  if (typeof claims.sub !== "string" || !claims.sub) throw new IdTokenError("ID token subject is missing");
  if (!audiences.includes(expected.clientId)) throw new IdTokenError("ID token audience is invalid");
  if (audiences.length > 1 && claims.azp !== expected.clientId) throw new IdTokenError("ID token authorized party is invalid");
  if (claims.azp !== undefined && claims.azp !== expected.clientId) throw new IdTokenError("ID token authorized party is invalid");
  if (typeof claims.exp !== "number" || claims.exp + skew <= expected.now) throw new IdTokenError("ID token has expired");
  if (typeof claims.iat !== "number" || claims.iat - skew > expected.now) throw new IdTokenError("ID token is not yet valid");
  if (typeof claims.nonce !== "string" || claims.nonce !== expected.nonce) throw new IdTokenError("ID token nonce is invalid");
  return claims;
}
