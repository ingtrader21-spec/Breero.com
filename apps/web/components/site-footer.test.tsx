import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SiteFooter } from "./site-footer";
import { SiteHeader } from "./site-header";

vi.mock("next/navigation", () => ({ usePathname: () => "/" }));

describe("SiteFooter", () => {
  it("provides the complete support, policy, and professional navigation contract", () => {
    render(<SiteFooter />);

    expect(screen.getByRole("contentinfo")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Help centre" })).toHaveAttribute("href", "/help");
    expect(screen.getByRole("link", { name: "Accessibility" })).toHaveAttribute("href", "/accessibility");
    expect(screen.getByRole("link", { name: "Refund, rescheduling & cancellation" })).toHaveAttribute(
      "href",
      "/refund-cancellation",
    );
    expect(screen.getByRole("link", { name: "Service fulfillment" })).toHaveAttribute(
      "href",
      "/service-fulfillment",
    );
    expect(screen.getByRole("link", { name: "Cookie preferences" })).toHaveAttribute(
      "href",
      "/cookie-preferences",
    );
    expect(screen.getByRole("link", { name: "Communication preferences" })).toHaveAttribute(
      "href",
      "/communications-preferences",
    );
    expect(screen.getByRole("link", { name: "Partner information" })).toHaveAttribute(
      "href",
      "/partners",
    );
    expect(screen.getByRole("link", { name: "Provider terms" })).toHaveAttribute(
      "href",
      "/provider-terms",
    );
    expect(screen.getByRole("link", { name: "Lead terms" })).toHaveAttribute("href", "/lead-terms");
    expect(screen.getByRole("link", { name: "Careers" })).toHaveAttribute("href", "/careers");
    expect(screen.getByRole("link", { name: "Press" })).toHaveAttribute("href", "/press");
  });
});

describe("SiteHeader", () => {
  it("opens and dismisses mobile navigation with Escape", () => {
    render(<SiteHeader />);
    fireEvent.click(screen.getByRole("button", { name: "Open menu" }));
    expect(screen.getByRole("navigation", { name: "Mobile navigation" })).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("navigation", { name: "Mobile navigation" })).not.toBeInTheDocument();
  });
});
