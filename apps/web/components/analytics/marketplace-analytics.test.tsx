import { ApiError } from "@breero/api-client";
import type { AnalyticsWindowQuery, MarketplaceMetrics } from "@breero/types";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { GENERATED_AT, emptyFixture, metricsFixture, providerFixture } from "./analytics-fixtures";
import { MarketplaceAnalytics } from "./marketplace-analytics";

type Loader = (window?: AnalyticsWindowQuery, signal?: AbortSignal) => Promise<MarketplaceMetrics>;
const { marketplace, provider } = vi.hoisted(() => ({
  marketplace: vi.fn<Loader>(),
  provider: vi.fn<Loader>(),
}));

vi.mock("@/lib/customer/api", () => ({ customerApi: { analytics: { marketplace, provider } } }));

function renderView(scope: "marketplace" | "provider" = "marketplace") {
  return render(<MarketplaceAnalytics scope={scope} eyebrow="Analytics" title="Marketplace analytics" description="Scoped metrics." />);
}

describe("MarketplaceAnalytics", () => {
  beforeEach(() => {
    marketplace.mockReset();
    provider.mockReset();
  });
  afterEach(() => vi.useRealTimers());

  it("shows a loading state before the projection resolves", () => {
    marketplace.mockReturnValue(new Promise(() => undefined));
    renderView();
    expect(screen.getByText("Loading analytics")).toBeInTheDocument();
  });

  it("renders projection values, freshness and withheld groups without fabricating numbers", async () => {
    vi.useFakeTimers({ now: new Date(GENERATED_AT), shouldAdvanceTime: true });
    marketplace.mockResolvedValue(metricsFixture());
    renderView();

    expect(await screen.findByText("Marketplace-wide view")).toBeInTheDocument();
    expect(screen.getByText("Current")).toBeInTheDocument();
    expect(screen.getByText("1 of 3 metric groups withheld")).toBeInTheDocument();

    const bookings = screen.getByRole("region", { name: "Bookings" });
    expect(within(bookings).getByText("4")).toBeInTheDocument();
    expect(within(bookings).getByText("50.0%")).toBeInTheDocument();
    expect(within(bookings).getByText("2 of 4")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Response time" })).getByText("3 min")).toBeInTheDocument();

    const finance = screen.getByRole("region", { name: "Finance" });
    expect(within(finance).getByText("Not yet available")).toBeInTheDocument();
    expect(within(finance).getByText(/Waiting on PAS-129/)).toBeInTheDocument();
    expect(within(finance).queryByRole("definition")).not.toBeInTheDocument();
    expect(marketplace).toHaveBeenCalledWith({ start: expect.stringMatching(/^2026-08-24T12:00:/) }, expect.any(AbortSignal));
    expect(provider).not.toHaveBeenCalled();
  });

  it("flags the view as stale once the projection max age passes", async () => {
    vi.useFakeTimers({ now: new Date(GENERATED_AT), shouldAdvanceTime: true });
    marketplace.mockResolvedValue(metricsFixture());
    renderView();
    await screen.findByText("Current");
    await act(async () => { vi.advanceTimersByTime(330_000); });
    expect(screen.getByText(/Stale — older than 5 minutes/)).toBeInTheDocument();
  });

  it("shows an empty state when the window has no recorded activity", async () => {
    marketplace.mockResolvedValue(emptyFixture());
    renderView();
    expect(await screen.findByText("No recorded activity in this window")).toBeInTheDocument();
    const bookings = screen.getByRole("region", { name: "Bookings" });
    expect(within(bookings).getByText("—")).toBeInTheDocument();
    expect(within(bookings).getByText("Not enough activity in this window to compute a rate")).toBeInTheDocument();
  });

  it("renders a restricted state and no metrics when the API denies scope", async () => {
    marketplace.mockRejectedValue(new ApiError("Forbidden", "forbidden", 403, "ANALYTICS_SCOPE_DENIED"));
    renderView();
    expect(await screen.findByText("Analytics access required")).toBeInTheDocument();
    expect(screen.queryByRole("region")).not.toBeInTheDocument();
    expect(screen.queryByText("Try again")).not.toBeInTheDocument();
  });

  it("uses only the provider-scoped endpoint for provider views and shows restricted groups", async () => {
    provider.mockResolvedValue(providerFixture());
    renderView("provider");
    expect(await screen.findByText("Your provider organization only")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Requests" })).getByText("Outside your scope")).toBeInTheDocument();
    expect(marketplace).not.toHaveBeenCalled();
  });

  it("offers retry after a transport error and recovers", async () => {
    marketplace.mockRejectedValueOnce(new ApiError("Down", "unavailable", 503)).mockResolvedValue(metricsFixture());
    renderView();
    expect(await screen.findByText("Analytics are temporarily unavailable")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("region", { name: "Bookings" })).toBeInTheDocument();
  });

  it("keeps the last result visible when a refresh fails (degraded)", async () => {
    marketplace.mockResolvedValueOnce(metricsFixture()).mockRejectedValue(new ApiError("Down", "network"));
    renderView();
    await screen.findByRole("region", { name: "Bookings" });
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Showing the previous result");
    expect(screen.getByRole("region", { name: "Bookings" })).toBeInTheDocument();
  });

  it("reloads with a new window when the reporting window changes", async () => {
    vi.useFakeTimers({ now: new Date(GENERATED_AT), shouldAdvanceTime: true });
    marketplace.mockResolvedValue(metricsFixture());
    renderView();
    await screen.findByRole("region", { name: "Bookings" });
    fireEvent.change(screen.getByLabelText("Reporting window"), { target: { value: "7" } });
    await screen.findByText("Current");
    expect(marketplace).toHaveBeenLastCalledWith({ start: expect.stringMatching(/^2026-09-16T12:00:/) }, expect.any(AbortSignal));
  });
});
