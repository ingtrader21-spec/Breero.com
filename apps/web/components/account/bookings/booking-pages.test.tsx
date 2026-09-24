import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@breero/api-client";
import type { Booking } from "@breero/types";
import BookingsPage from "@/app/account/bookings/page";
import BookingDetail from "@/app/account/bookings/[id]/page";

const api = vi.hoisted(() => ({ mine: vi.fn(), getMine: vi.fn(), cancelMine: vi.fn(), id: "booking-a", query: "" }));
vi.mock("@/lib/customer/api", () => ({ customerApi: { bookings: api } }));
vi.mock("next/navigation", () => ({ useParams: () => ({ id: api.id }), useSearchParams: () => new URLSearchParams(api.query) }));
const booking: Booking = { id: "booking-a", reference: "BR-A", status: "CONFIRMED", total_amount: "120.00", currency: "USD", window_start: "2026-09-25T10:00:00Z", window_end: "2026-09-25T12:00:00Z", payment_required: false };
const page = (items: Booking[], number = 1, total = items.length) => ({ items, page: number, page_size: 20, total });
beforeEach(() => { vi.clearAllMocks(); api.id = "booking-a"; api.query = ""; api.mine.mockResolvedValue(page([booking])); api.getMine.mockResolvedValue(booking); });

describe("customer booking list", () => {
  it("announces loading and displays an empty response without records", async () => {
    api.mine.mockResolvedValue(page([]));
    render(<BookingsPage />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading your bookings");
    expect(await screen.findByRole("heading", { name: "No bookings here yet" })).toBeVisible();
    expect(screen.queryByText("BR-A")).not.toBeInTheDocument();
  });
  it("keeps expired bookings in history and normalizes unknown filters", async () => {
    api.query = "view=nonsense";
    api.mine.mockResolvedValue(page([{ ...booking, status: "EXPIRED" }]));
    render(<BookingsPage />);
    expect(await screen.findByRole("heading", { name: /No active bookings/ })).toBeVisible();
    expect(screen.getByRole("link", { name: "Active" })).toHaveAttribute("aria-current", "page");
  });
  it("loads subsequent pages even when the current page has no active matches", async () => {
    api.mine.mockResolvedValueOnce(page([{ ...booking, status: "COMPLETED" }], 1, 21)).mockResolvedValueOnce(page([{ ...booking, reference: "BR-B" }], 2, 21));
    render(<BookingsPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Next page" }));
    expect(await screen.findByText("BR-B")).toBeVisible();
    expect(api.mine).toHaveBeenLastCalledWith({ page: 2, pageSize: 20 }, expect.any(AbortSignal));
    expect(screen.getByText(/Page 2 of 2/)).toBeVisible();
  });
  it.each([["forbidden", "Access restricted", false], ["authentication", "Sign in to view bookings", false], ["network", "Connection interrupted", true], ["server", "Bookings aren’t available", true]] as const)("handles %s safely", async (kind, title, retry) => {
    api.mine.mockRejectedValue(new ApiError("private backend detail", kind));
    render(<BookingsPage />);
    expect(await screen.findByRole("heading", { name: title })).toBeVisible();
    expect(screen.queryByText(/private backend detail/)).not.toBeInTheDocument();
    expect(!!screen.queryByRole("button", { name: "Try again" })).toBe(retry);
  });
  it("recovers from an outage using retry", async () => {
    api.mine.mockRejectedValueOnce(new ApiError("outage", "unavailable", 503)).mockResolvedValueOnce(page([booking]));
    render(<BookingsPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Try again" }));
    expect(await screen.findByText("BR-A")).toBeVisible();
  });
});

describe("customer booking detail", () => {
  it("does not show a previous booking or a late response after changing routes", async () => {
    let resolveOld!: (value: Booking) => void;
    api.getMine.mockImplementationOnce(() => new Promise<Booking>((resolve) => { resolveOld = resolve; })).mockResolvedValueOnce({ ...booking, id: "booking-b", reference: "BR-B" });
    const view = render(<BookingDetail />);
    api.id = "booking-b";
    view.rerender(<BookingDetail />);
    await screen.findByText("Booking BR-B");
    await act(async () => resolveOld(booking));
    expect(screen.queryByText("Booking BR-A")).not.toBeInTheDocument();
  });
  it("clears the previous record while a new route is loading", async () => {
    const view = render(<BookingDetail />);
    await screen.findByText("Booking BR-A");
    api.getMine.mockImplementationOnce(() => new Promise(() => undefined));
    api.id = "booking-b";
    view.rerender(<BookingDetail />);
    expect(screen.queryByText("Booking BR-A")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Loading booking details");
  });
  it("keeps a navigation escape on a missing record", async () => {
    api.getMine.mockRejectedValue(new ApiError("missing", "not_found", 404));
    render(<BookingDetail />);
    await screen.findByRole("heading", { name: "Booking not available" });
    expect(screen.getByRole("link", { name: /Back to bookings/ })).toHaveAttribute("href", "/account/bookings");
  });
  it.each(["IN_PROGRESS", "EN_ROUTE", "EXPIRED", "COMPLETED", "UNKNOWN_STATUS"])("disables cancellation for %s", async (status) => {
    api.getMine.mockResolvedValue({ ...booking, status });
    render(<BookingDetail />);
    await screen.findByText("Booking BR-A");
    expect(screen.getByRole("button", { name: "Cancel booking" })).toBeDisabled();
  });
  it("uses the cancellation response and does not offer duplicate cancellation", async () => {
    api.cancelMine.mockResolvedValue({ ...booking, status: "CANCELLED" });
    render(<BookingDetail />);
    fireEvent.click(await screen.findByRole("button", { name: "Cancel booking" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Cancel booking" })).toBeDisabled());
    expect(screen.getByText("Cancelled")).toBeVisible();
  });
  it("does not instruct payment when no payment flow exists", async () => {
    api.getMine.mockResolvedValue({ ...booking, payment_required: true });
    render(<BookingDetail />);
    await screen.findByText("Booking BR-A");
    expect(screen.queryByText(/Complete the secure payment step/)).not.toBeInTheDocument();
    expect(screen.getByText(/Online payment is not available in this workspace/)).toBeVisible();
  });
});
