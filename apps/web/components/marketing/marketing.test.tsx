import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { intakeServices, marketingServices } from "@/content/services";
import { FAQ } from "./FAQ";
import { Hero } from "./Hero";
import { PublicIntakeForm } from "./PublicIntakeForm";
import { ServiceCard } from "./ServiceCard";

const capabilities = {
  request_intake: true,
  instant_booking: false,
  online_payments: false,
  automatic_assignment: false,
  provider_self_service: false,
  marketplace_matching: false,
  messaging: false,
  reviews: false,
};
const liveServices = [{ id: "service-1", slug: "plumbing", name: "Plumbing", is_active: true }];

function stubCatalog({ instantBooking = false }: { instantBooking?: boolean } = {}) {
  vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(new Response(
    JSON.stringify(url.includes("capabilities")
      ? { ...capabilities, instant_booking: instantBooking }
      : liveServices),
    { status: 200, headers: { "content-type": "application/json" } },
  ))));
}

describe("marketing system", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("uses the canonical request-first CTA", () => {
    render(
      <Hero
        title="Home services"
        description="Trusted help"
        image={{ src: "/images/hero/home-hero.webp", alt: "Professional arriving" }}
      />,
    );
    expect(screen.getByRole("link", { name: "Request a service" })).toHaveAttribute(
      "href",
      "/request-service",
    );
  });

  it("links service cards to public service pages", () => {
    render(<ServiceCard service={marketingServices[0]} />);
    expect(screen.getByRole("link")).toHaveAttribute("href", "/services/plumbing");
  });

  it("keeps intake service slugs unique and includes the expanded catalog", () => {
    expect(new Set(intakeServices.map((service) => service.slug)).size).toBe(intakeServices.length);
    expect(intakeServices.map((service) => service.slug)).toEqual(expect.arrayContaining([
      "roofing", "flooring", "pest-control", "lawn-landscaping", "garage-door",
    ]));
  });

  it("renders accessible FAQ controls", () => {
    render(<FAQ limit={2} />);
    expect(screen.getAllByText(/How|pricing/i).length).toBeGreaterThan(0);
  });

  it("labels preferred timing as a request when instant booking is disabled", async () => {
    stubCatalog();
    render(<PublicIntakeForm kind="service" />);

    await waitFor(() => expect(screen.getByLabelText("Preferred date (request only)")).toBeEnabled());
    expect(screen.getByRole("button", { name: "Request service" })).toBeEnabled();
  });

  it("keeps timing request-only when instant booking is enabled", async () => {
    stubCatalog({ instantBooking: true });
    render(<PublicIntakeForm kind="service" />);

    await waitFor(() => expect(screen.getByLabelText("Preferred date (request only)")).toBeEnabled());
    expect(screen.getByLabelText("Preferred local time (request only)")).toBeEnabled();
    expect(screen.queryByLabelText("Appointment date")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Appointment time")).not.toBeInTheDocument();
  });

  it("uses the live service catalog for provider interest", async () => {
    stubCatalog();
    render(<PublicIntakeForm kind="provider" />);

    await waitFor(() => expect(screen.getByRole("option", { name: "Plumbing" })).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Submit partner interest" })).toBeEnabled();
  });

  it("exposes every backend-supported contact category", () => {
    render(<PublicIntakeForm kind="contact" />);

    expect(screen.getByRole("option", { name: "Privacy request" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Provider question" })).toBeInTheDocument();
    expect(screen.getByLabelText("Message")).toHaveAttribute("minlength", "10");
  });

  it("keeps the standard service catalog available when live catalog refresh fails", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string) => url.includes("capabilities")
      ? Promise.resolve(new Response(JSON.stringify({ request_intake: true }), { status: 200 }))
      : Promise.reject(new Error("catalog unavailable"))));

    render(<PublicIntakeForm kind="service" />);

    await waitFor(() => expect(screen.getByText(/standard service list is shown/i)).toBeInTheDocument());
    expect(screen.getByRole("option", { name: "Roofing" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Request service" })).toBeEnabled();
  });

  it("does not offer fallback services after an authoritative empty catalog response", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify(
      url.includes("capabilities") ? { request_intake: true } : [],
    ), { status: 200 }))));

    render(<PublicIntakeForm kind="service" />);

    await waitFor(() => expect(screen.getByText(/no services are currently accepting requests/i)).toBeInTheDocument());
    expect(screen.queryByRole("option", { name: "Roofing" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Request service" })).toBeDisabled();
  });

  it("reports capability failures separately and keeps submission disabled", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string) => url.includes("capabilities")
      ? Promise.reject(new Error("capabilities unavailable"))
      : Promise.resolve(new Response(JSON.stringify(liveServices), { status: 200 }))));

    render(<PublicIntakeForm kind="service" />);

    await waitFor(() => expect(screen.getByText(/request availability could not be verified/i)).toBeInTheDocument());
    expect(screen.queryByText(/standard service list is shown/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Request service" })).toBeDisabled();
  });
});
