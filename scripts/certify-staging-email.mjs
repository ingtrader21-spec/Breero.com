const webBase = process.env.STAGING_WEB_BASE_URL;
const apiBase = process.env.STAGING_API_BASE_URL;
const accessToken = process.env.STAGING_ACCESS_TOKEN || "";
const allowWrite = process.env.STAGING_ALLOW_EMAIL_CANARY === "1";
const canarySenderId = process.env.STAGING_CANARY_SENDER_ID || "";
const canaryCredentialId = process.env.STAGING_CANARY_CREDENTIAL_ID || "";
const canaryRecipient = process.env.STAGING_CANARY_RECIPIENT || "";

if (!webBase || !apiBase) {
  throw new Error("STAGING_WEB_BASE_URL and STAGING_API_BASE_URL are required");
}

function allowedStagingUrl(value, label) {
  const url = new URL(value);
  if (url.protocol !== "https:") throw new Error(`${label} must use HTTPS`);
  const host = url.hostname.toLowerCase();
  const allowed = host === "staging.breero.com" || host === "api-staging.breero.com" || host.endsWith(".staging.breero.com");
  if (!allowed) throw new Error(`${label} must point to an approved BREERO staging hostname`);
  return url.origin;
}

const webOrigin = allowedStagingUrl(webBase, "STAGING_WEB_BASE_URL");
const apiOrigin = allowedStagingUrl(apiBase, "STAGING_API_BASE_URL");
const headers = accessToken ? { Authorization: `Bearer ${accessToken}` } : {};

async function request(path, init = {}) {
  const response = await fetch(`${apiOrigin}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...headers, ...(init.headers || {}) },
    redirect: "manual",
  });
  const text = await response.text();
  let body = null;
  if (text) {
    try { body = JSON.parse(text); } catch { body = text; }
  }
  if (!response.ok) throw new Error(`${init.method || "GET"} ${path} -> ${response.status}: ${String(text).slice(0, 300)}`);
  return body;
}

function assertNoSecrets(value, label) {
  const serialized = JSON.stringify(value).toLowerCase();
  for (const forbidden of ["password", "secret_ref", "smtp_password", "api_key"]) {
    if (serialized.includes(forbidden)) throw new Error(`${label} exposed forbidden field: ${forbidden}`);
  }
}

const webLogin = await fetch(`${webOrigin}/login`, { redirect: "manual" });
if (![200, 301, 302, 307, 308].includes(webLogin.status)) {
  throw new Error(`staging web /login is unavailable: ${webLogin.status}`);
}

const ready = await request("/health/ready");
if (ready?.status !== "ready" || ready?.postgres !== "ok" || ready?.schema !== "ok" || ready?.redis !== "ok") {
  throw new Error(`staging API is not ready: ${JSON.stringify(ready)}`);
}

const loginMode = await request("/api/v1/auth/login-mode");
if (!loginMode?.mode) throw new Error("staging login-mode contract is missing");

console.log(`STAGING_REACHABILITY=PASS web=${webOrigin} api=${apiOrigin}`);
console.log(`STAGING_DEPENDENCIES=PASS schema=${ready.schema} postgres=${ready.postgres} redis=${ready.redis}`);
console.log(`STAGING_LOGIN_MODE=PASS mode=${loginMode.mode}`);

if (!accessToken) {
  console.log("STAGING_AUTHENTICATED_CERTIFICATION=BLOCKED reason=STAGING_ACCESS_TOKEN_missing");
  process.exit(2);
}

const context = await request("/api/v1/auth/context");
if (!context?.dashboard_path || !Array.isArray(context?.permissions)) throw new Error("portal context contract is invalid");
console.log(`STAGING_PORTAL_CONTEXT=PASS dashboard=${context.dashboard_path}`);

const [domains, senders, credentials, outbox] = await Promise.all([
  request("/api/v1/email/domains"),
  request("/api/v1/email/senders"),
  request("/api/v1/email/credentials"),
  request("/api/v1/email/outbox"),
]);
assertNoSecrets(credentials, "credential list");
assertNoSecrets(outbox, "outbox list");
console.log(`STAGING_EMAIL_READ_CONTRACT=PASS domains=${domains.length} senders=${senders.length} credentials=${credentials.length} outbox=${outbox.length}`);

if (!allowWrite) {
  console.log("STAGING_EMAIL_CANARY=SKIPPED reason=STAGING_ALLOW_EMAIL_CANARY_not_enabled");
  process.exit(0);
}

if (!canarySenderId || !canaryCredentialId || !canaryRecipient) {
  throw new Error("write canary requires STAGING_CANARY_SENDER_ID, STAGING_CANARY_CREDENTIAL_ID and STAGING_CANARY_RECIPIENT");
}

const sender = senders.find((item) => item.id === canarySenderId);
const credential = credentials.find((item) => item.id === canaryCredentialId);
if (!sender) throw new Error("configured canary sender is not visible in authenticated tenant scope");
if (!credential) throw new Error("configured canary credential is not visible in authenticated tenant scope");
if (!credential.secret_configured) throw new Error("configured canary credential has no runtime secret reference");
const domain = domains.find((item) => item.id === sender.domain_id);
if (!domain || domain.verification_status !== "VERIFIED") throw new Error("configured canary sender domain is not verified");

const idempotencyKey = `staging-cert-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
const message = await request("/api/v1/email/messages", {
  method: "POST",
  body: JSON.stringify({
    brand_key: sender.brand_key,
    vendor_id: sender.vendor_id,
    sender_id: sender.id,
    credential_id: credential.id,
    to_email: canaryRecipient,
    subject: "BREERO staging email certification",
    text_body: "Automated BREERO staging certification canary. No production environment is targeted.",
    idempotency_key: idempotencyKey,
  }),
});
assertNoSecrets(message, "compose response");

const refreshedOutbox = await request("/api/v1/email/outbox");
const event = refreshedOutbox.find((item) => item.message_id === message.id);
if (!event) throw new Error("compose succeeded but no durable email outbox event was found");
assertNoSecrets(event, "canary outbox event");
console.log(`STAGING_EMAIL_CANARY=PASS message=${message.id} outbox=${event.id} status=${event.status}`);
