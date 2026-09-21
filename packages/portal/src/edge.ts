const CSP_NONCE_PATTERN = /^[A-Za-z0-9_-]{16,128}$/;

export function buildContentSecurityPolicy(nonce: string, production = true): string {
  if (!CSP_NONCE_PATTERN.test(nonce)) {
    throw new TypeError("CSP nonce must be a bounded base64url-safe value");
  }

  const directives = [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'`,
    "style-src 'self'",
    "img-src 'self' data:",
    "font-src 'self'",
    "connect-src 'self'",
    "media-src 'none'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "worker-src 'self' blob:",
    "manifest-src 'self'",
  ];
  if (production) directives.push("upgrade-insecure-requests");
  return directives.join("; ");
}
