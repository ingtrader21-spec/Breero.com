import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { SECTIONS } from "../components/PartnerApp";
import { FinanceSection } from "../components/sections/FinanceSection";
import { OnboardingView } from "../components/sections/OnboardingSection";
import { profilePatch } from "../components/sections/ProfileSection";
import { validateWorker } from "../components/sections/TeamSection";
import { isOfferActionable } from "../components/sections/WorkSection";
import { formFromApplication } from "../lib/onboarding";
import type { OnboardingChecklist } from "../lib/types";
import { application } from "./fixtures";

function checklist(overrides: Partial<OnboardingChecklist> = {}): OnboardingChecklist {
  return {
    application_id: "app-1",
    status: "DRAFT",
    version: 4,
    editable: true,
    submittable: false,
    missing: ["services"],
    requested_information: null,
    decision_reason: null,
    submitted_at: null,
    decided_at: null,
    ...overrides,
  };
}

function renderOnboarding(list: OnboardingChecklist, activeStep = "business") {
  const app = application({ status: list.status });
  return renderToStaticMarkup(
    <OnboardingView
      application={app}
      checklist={list}
      form={formFromApplication(app)}
      activeStep={activeStep}
      busy={false}
      onSelectStep={() => undefined}
      onFormChange={() => undefined}
      onSave={() => undefined}
      onSubmit={() => undefined}
      navigate={() => undefined}
    />,
  );
}

describe("partner navigation", () => {
  it("exposes every provider self-service area and no placeholder sections", () => {
    expect(SECTIONS.map((item) => item.key)).toEqual([
      "onboarding", "profile", "services", "skills", "team", "availability", "qualifications", "work", "finance",
    ]);
  });
});

describe("onboarding wizard", () => {
  it("lets a draft provider edit and blocks submission until complete", () => {
    const html = renderOnboarding(checklist());
    expect(html).toContain("Diaz Plumbing LLC");
    expect(html).toContain("Save progress");
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>Submit application<\/button>/);
    expect(html).toContain("Outstanding: Services offered.");
  });

  it("shows requested information and offers resubmission", () => {
    const html = renderOnboarding(
      checklist({ status: "INFORMATION_REQUESTED", requested_information: "Upload your current COI", submittable: true, missing: [] }),
    );
    expect(html).toContain("Information requested");
    expect(html).toContain("BREERO requested: Upload your current COI");
    expect(html).toMatch(/<button[^>]*>Resubmit application<\/button>/);
    expect(html).not.toMatch(/<button[^>]*disabled=""[^>]*>Resubmit application/);
  });

  it("locks the wizard while under review", () => {
    const html = renderOnboarding(checklist({ status: "PENDING", editable: false, submittable: false, missing: [] }));
    expect(html).toContain("Under review");
    expect(html).not.toContain("Save progress");
    expect(html).not.toContain("Submit application");
    expect(html).toMatch(/<input[^>]*disabled=""/);
  });

  it("shows rejection and approval outcomes", () => {
    expect(renderOnboarding(checklist({ status: "REJECTED", editable: false, decision_reason: "Unverifiable license" }))).toContain(
      "Decision note: Unverifiable license",
    );
    expect(renderOnboarding(checklist({ status: "APPROVED", editable: false, missing: [] }))).toContain("Approved");
  });

  it("routes externally managed steps to their section", () => {
    const html = renderOnboarding(checklist({ missing: ["licenses", "insurance"] }), "qualifications");
    expect(html).toContain("Still needed: Submitted license, Submitted insurance.");
    expect(html).toContain("Add and submit qualifications");
  });
});

describe("finance integration point", () => {
  it("renders no money-moving controls", () => {
    const html = renderToStaticMarkup(<FinanceSection />);
    expect(html).toContain("Earnings &amp; payouts");
    expect(html).not.toMatch(/<button|<form/);
  });
});

describe("section helpers", () => {
  it("sends only changed profile fields within the allowed radius", () => {
    const profile = { id: "v", legal_name: "A LLC", display_name: "A", email: "a@x.test", phone: "+17135550100", status: "PENDING" as const, service_radius_meters: 40234 };
    expect(profilePatch({ legalName: "A LLC", displayName: "A Pro", phone: "+17135550100", radiusMiles: "25" }, profile)).toEqual({
      patch: { display_name: "A Pro" },
      errors: [],
    });
    expect(profilePatch({ legalName: "A LLC", displayName: "A", phone: "+17135550100", radiusMiles: "900" }, profile).errors).toHaveLength(1);
  });

  it("validates new team members", () => {
    expect(validateWorker({ first_name: "Luis", last_name: "Ramos", email: "luis@x.test", phone: "+17135550111" })).toEqual([]);
    expect(validateWorker({ first_name: "", last_name: "Ramos", email: "nope", phone: "1" })).toHaveLength(3);
  });

  it("only allows decisions on live pending offers", () => {
    const now = Date.parse("2026-09-25T12:00:00Z");
    expect(isOfferActionable({ status: "PENDING", expires_at: "2026-09-25T13:00:00Z" }, now)).toBe(true);
    expect(isOfferActionable({ status: "PENDING", expires_at: "2026-09-25T11:00:00Z" }, now)).toBe(false);
    expect(isOfferActionable({ status: "ACCEPTED", expires_at: "2026-09-25T13:00:00Z" }, now)).toBe(false);
  });
});
