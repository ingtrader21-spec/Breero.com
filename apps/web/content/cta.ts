export type CtaDefinition = {
  id: string;
  label: string;
  href: string;
  analytics: string;
  requiredCapability?: string;
  fallbackHref?: string;
};

export const ctas = {
  requestService: {
    id: "request-service",
    label: "Request a service",
    href: "/request-service",
    analytics: "request-service",
    requiredCapability: "request_intake",
    fallbackHref: "/contact",
  },
  exploreServices: {
    id: "explore-services",
    label: "Explore services",
    href: "/services",
    analytics: "explore-services",
  },
  partnerInterest: {
    id: "partner-interest",
    label: "Become a BREERO partner",
    href: "/partners#interest",
    analytics: "partner-interest",
    fallbackHref: "/contact",
  },
  contactSupport: {
    id: "contact-support",
    label: "Talk with BREERO",
    href: "/contact",
    analytics: "contact-support",
  },
} as const satisfies Record<string, CtaDefinition>;
