import type { PortalRuntimeConfig } from "@breero/portal";

export const portalRuntime = {
  kind: "partner",
  title: "BREERO Partner",
  eyebrow: "Provider command center",
  allowedRoles: ["vendor_admin"],
  apiRules: [
    { prefix: "/portal/capabilities", methods: ["GET"] },
    { prefix: "/portal/provider", methods: ["GET"] },
    { prefix: "/provider", methods: ["GET", "POST", "PUT", "PATCH", "DELETE"] },
    { prefix: "/jobs", methods: ["GET", "POST", "PATCH"] },
    { prefix: "/vendors", methods: ["GET", "POST"] },
    { prefix: "/services", methods: ["GET"] },
  ],
} as const satisfies PortalRuntimeConfig;
