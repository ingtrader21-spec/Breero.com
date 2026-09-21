import type { PortalRuntimeConfig } from "@breero/portal";

export const portalRuntime = {
  kind: "admin",
  title: "BREERO Administration",
  eyebrow: "Governance, finance, and platform control",
  allowedRoles: ["admin", "superadmin", "finance"],
  apiRules: [
    { prefix: "/portal/capabilities", methods: ["GET"] },
    { prefix: "/portal/admin", methods: ["GET"] },
    { prefix: "/admin", methods: ["GET", "POST", "PUT", "PATCH", "DELETE"] },
    { prefix: "/finance", methods: ["GET", "POST", "PUT", "PATCH"] },
    { prefix: "/operations", methods: ["GET", "POST", "PATCH"] },
    { prefix: "/jobs", methods: ["GET", "POST", "PATCH"] },
    { prefix: "/vendors", methods: ["GET", "PATCH"] },
    { prefix: "/bookings", methods: ["GET", "POST", "PATCH"] },
    { prefix: "/services", methods: ["GET", "POST", "PUT", "PATCH", "DELETE"] },
    { prefix: "/integrations", methods: ["GET", "POST", "PATCH"] },
  ],
} as const satisfies PortalRuntimeConfig;
