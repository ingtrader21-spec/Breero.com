import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { caseEntries } from "@/lib/support/test-fixtures";
import { CaseTimeline } from "./case-timeline";

describe("CaseTimeline", () => {
  it("never renders internal notes or internal evidence to a customer", () => {
    render(<CaseTimeline viewer={{ kind: "customer", canReadInternal: false }} entries={caseEntries} />);

    const list = screen.getByRole("list", { name: "Case activity" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(3);
    expect(screen.queryByText(/Second complaint/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Mis-tagged private note/)).not.toBeInTheDocument();
    expect(screen.queryByText("invoice.pdf")).not.toBeInTheDocument();
    expect(screen.queryByText(/Internal note — not shared/)).not.toBeInTheDocument();
    expect(screen.getAllByText("Visible to customer")).toHaveLength(3);
  });

  it("labels internal notes distinctly for staff", () => {
    render(<CaseTimeline viewer={{ kind: "staff", canReadInternal: true }} entries={caseEntries} />);

    expect(screen.getAllByRole("listitem")).toHaveLength(caseEntries.length);
    const note = screen.getByText(/Second complaint/).closest("li");
    expect(note).not.toBeNull();
    expect(within(note as HTMLElement).getByText("Internal note — not shared")).toBeInTheDocument();
  });

  it("shows evidence scan state and blocks download of unscanned files", () => {
    render(<CaseTimeline viewer={{ kind: "staff", canReadInternal: true }} entries={caseEntries} />);

    const clean = screen.getByText("doorbell.jpg").closest("li") as HTMLElement;
    expect(within(clean).getByText("Scanned clean")).toBeInTheDocument();
    expect(within(clean).queryByText(/Download is blocked/)).not.toBeInTheDocument();

    const quarantined = screen.getByText("invoice.pdf").closest("li") as HTMLElement;
    expect(within(quarantined).getByText("Quarantined")).toBeInTheDocument();
    expect(within(quarantined).getByText(/Download is blocked/)).toBeInTheDocument();
    expect(within(quarantined).queryByRole("link")).not.toBeInTheDocument();
  });

  it("describes status changes and escalations in words", () => {
    render(<CaseTimeline viewer={{ kind: "staff", canReadInternal: true }} entries={caseEntries} />);

    expect(screen.getByText("Status changed from Open to Escalated.")).toBeInTheDocument();
    expect(screen.getByText("Escalated to Trust & safety: Repeated no-show.")).toBeInTheDocument();
    expect(screen.getByText("2026-09-20T10:21:00Z")).toHaveAttribute("datetime", "2026-09-20T10:21:00Z");
  });

  it("shows an empty state when nothing is visible", () => {
    render(<CaseTimeline viewer={{ kind: "none", canReadInternal: false }} entries={caseEntries} />);

    expect(screen.queryByRole("list")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "No case activity to show" })).toBeInTheDocument();
  });
});
