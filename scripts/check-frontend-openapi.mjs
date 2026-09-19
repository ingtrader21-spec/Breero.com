import { readFileSync } from "node:fs";

const document = JSON.parse(readFileSync(new URL("../apps/api/openapi.json", import.meta.url), "utf8"));

// Release contract consumed by the public site and every authenticated portal.
// This is intentionally method-specific: rendering a shell is not sufficient when
// a browser command would still resolve to a 404 or the wrong HTTP verb.
const required = {
  "/api/v2/capabilities": ["get"],
  "/api/v1/public/capabilities": ["get"],
  "/api/v1/auth/login": ["post"],
  "/api/v1/auth/register": ["post"],
  "/api/v1/auth/refresh": ["post"],
  "/api/v1/auth/logout": ["post"],
  "/api/v1/auth/logout-all": ["post"],
  "/api/v1/auth/password/forgot": ["post"],
  "/api/v1/auth/password/reset": ["post"],
  "/api/v1/auth/email/verify": ["post"],
  "/api/v1/auth/context": ["get"],
  "/api/v1/auth/access/catalog": ["get"],
  "/api/v1/auth/access/users/{user_id}": ["get", "put"],

  "/api/v1/services": ["get"],
  "/api/v1/services/{service_id}": ["get"],
  "/api/v1/services/{service_id}/questions": ["get"],
  "/api/v1/service-requests": ["post"],
  "/api/v1/availability/search": ["post"],
  "/api/v1/bookings": ["post"],
  "/api/v1/bookings/{booking_id}/confirmation": ["get"],
  "/api/v1/contact": ["post"],
  "/api/v1/provider-interest": ["post"],
  "/api/v1/privacy-requests": ["post"],
  "/api/v1/communications/preferences": ["post"],
  "/api/v1/customer/profile": ["get", "patch"],
  "/api/v1/customer/addresses": ["get", "post"],
  "/api/v1/customer/addresses/{address_id}": ["patch", "delete"],
  "/api/v1/customer/bookings": ["get"],
  "/api/v1/customer/bookings/{booking_id}": ["get"],
  "/api/v1/customer/bookings/{booking_id}/cancel": ["post"],
  "/api/v1/customer/quotes": ["get"],
  "/api/v1/customer/quotes/{quote_id}": ["get"],
  "/api/v1/customer/quotes/{quote_id}/decision": ["post"],

  "/api/v1/portal/capabilities": ["get"],
  "/api/v1/portal/provider/overview": ["get"],
  "/api/v1/portal/provider/jobs": ["get"],
  "/api/v1/portal/provider/workers": ["get"],
  "/api/v1/portal/provider/credentials": ["get"],
  "/api/v1/portal/provider/earnings": ["get"],
  "/api/v1/portal/provider/payout-batches": ["get"],
  "/api/v1/portal/operations/overview": ["get"],
  "/api/v1/portal/admin/overview": ["get"],
  "/api/v1/portal/admin/audit": ["get"],

  "/api/v1/provider/profile": ["get", "patch"],
  "/api/v1/provider/onboarding": ["get", "patch"],
  "/api/v1/provider/onboarding/submit": ["post"],
  "/api/v1/provider/services": ["get", "post"],
  "/api/v1/provider/services/{provider_service_id}": ["patch", "delete"],
  "/api/v1/provider/skills": ["get", "post"],
  "/api/v1/provider/skills/{provider_skill_id}": ["delete"],
  "/api/v1/vendors/{vendor_id}/workers": ["post"],

  "/api/v1/operations/dispatcher/queue": ["get"],
  "/api/v1/operations/dispatcher/queue/{request_id}": ["patch"],
  "/api/v1/operations/jobs/{job_id}/match": ["post"],
  "/api/v1/operations/jobs/{job_id}/assign": ["post"],
  "/api/v1/operations/bookings/{booking_id}/confirm": ["post"],
  "/api/v1/operations/workers/{worker_id}/booking-coverage": ["put"],
  "/api/v1/operations/vendors/{vendor_id}/status": ["patch"],

  "/api/v1/admin/users": ["get"],
  "/api/v1/admin/users/{user_id}": ["patch"],
  "/api/v1/admin/service-zones": ["get", "post"],
  "/api/v1/admin/service-zones/{service_area_id}": ["get", "patch", "delete"],
  "/api/v1/admin/postal-codes": ["get", "post"],
  "/api/v1/admin/postal-codes/{postal_code_id}": ["patch", "delete"],
  "/api/v1/integrations/config": ["get"],
  "/api/v1/integrations/operations": ["get"],
  "/api/v1/integrations/outbox/activate-pending": ["post"],
  "/api/v1/integrations/outbox/park-unconfigured": ["post"],
};

// The current production release is quote-only and operator-controlled.
const forbidden = {
  "/api/v1/bookings/{booking_id}/payment": ["post"],
  "/api/v1/payments/intents": ["post"],
  "/api/v1/payments/webhooks/stripe": ["post"],
};

const missing = [];
for (const [path, methods] of Object.entries(required)) {
  for (const method of methods) {
    if (!document.paths?.[path]?.[method]) missing.push(`${method.toUpperCase()} ${path}`);
  }
}
if (missing.length) {
  console.error(`Frontend API contract is missing:\n${missing.join("\n")}`);
  process.exit(1);
}

const exposed = [];
for (const [path, methods] of Object.entries(forbidden)) {
  for (const method of methods) {
    if (document.paths?.[path]?.[method]) exposed.push(`${method.toUpperCase()} ${path}`);
  }
}
if (exposed.length) {
  console.error(`Payment-disabled API contract exposes forbidden payment routes:\n${exposed.join("\n")}`);
  process.exit(1);
}

const enumExpectations = {
  QuestionType: ["text", "textarea", "number", "boolean", "single_choice", "multi_choice"],
  UserRole: ["customer", "vendor_admin", "technician", "operations", "finance", "admin"],
  BookingStatus: ["PENDING_PAYMENT", "CONFIRMED", "CANCELLED", "EXPIRED"],
  WorkRequestStatus: [
    "DRAFT", "SUBMITTED", "PENDING_CUSTOMER", "APPROVED_PENDING_PAYMENT",
    "APPROVED", "DECLINED", "PAID", "CANCELLED", "EXPIRED",
  ],
};
for (const [schema, expected] of Object.entries(enumExpectations)) {
  const actual = document.components?.schemas?.[schema]?.enum ?? [];
  for (const value of expected) if (!actual.includes(value)) missing.push(`${schema}.${value}`);
}
if (missing.length) {
  console.error(`Frontend enum contract is missing:\n${missing.join("\n")}`);
  process.exit(1);
}

console.log(
  `BREERO frontend API contract verified: ${Object.keys(required).length} required paths; ` +
    "zero forbidden payment mutation routes.",
);
