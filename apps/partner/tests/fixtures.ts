import type { ProviderApplication } from "../lib/types";

export function application(overrides: Partial<ProviderApplication> = {}): ProviderApplication {
  return {
    id: "app-1",
    status: "DRAFT",
    identity: { full_name: "Ana Diaz" },
    business: { legal_name: "Diaz Plumbing LLC", display_name: "Diaz Plumbing", internal_note: "kept" },
    contact_details: { email: "ana@diaz.test", phone: "+17135550100" },
    services: [],
    skills: [],
    service_areas: [],
    postal_codes: ["77001"],
    availability: {},
    capacity: {},
    licenses: [],
    insurance: [],
    compliance_documents: [],
    version: 4,
    submitted_at: null,
    decided_at: null,
    decision_reason: null,
    requested_information: null,
    ...overrides,
  };
}
