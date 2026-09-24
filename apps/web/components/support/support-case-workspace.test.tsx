import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PortalContext } from "@breero/types";
import { assignment, customerContext, portalContext } from "@/lib/support/test-fixtures";
import { SupportCaseWorkspace } from "./support-case-workspace";

const { loadPortalContext } = vi.hoisted(() => ({
  loadPortalContext: vi.fn<() => Promise<PortalContext>>(),
}));

vi.mock("@/lib/portal", () => ({ loadPortalContext }));

beforeEach(() => {
  loadPortalContext.mockReset();
  loadPortalContext.mockResolvedValue(portalContext());
});

describe("SupportCaseWorkspace", () => {
  it("shows a named loading state while access is unresolved", () => {
    loadPortalContext.mockImplementationOnce(() => new Promise<PortalContext>(() => undefined));
    render(<SupportCaseWorkspace />);

    expect(screen.getByRole("status")).toHaveTextContent("Checking your support case access");
  });

  it("shows a retryable error and recovers", async () => {
    loadPortalContext.mockRejectedValueOnce(new Error("offline"));
    render(<SupportCaseWorkspace />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("We couldn’t confirm your support access");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(await screen.findByRole("heading", { level: 1, name: "Support cases" })).toBeInTheDocument();
    expect(loadPortalContext).toHaveBeenCalledTimes(2);
  });

  it("restricts customers without revealing case content", async () => {
    loadPortalContext.mockResolvedValueOnce(customerContext);
    render(<SupportCaseWorkspace />);

    expect(await screen.findByRole("heading", { name: "Support cases are restricted" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to your dashboard" })).toHaveAttribute("href", "/account");
    expect(screen.queryByText("Your case access")).not.toBeInTheDocument();
  });

  it("restricts support staff without a case read permission", async () => {
    loadPortalContext.mockResolvedValueOnce(portalContext({ permissions: ["support.customers.read"] }));
    render(<SupportCaseWorkspace />);

    expect(await screen.findByRole("heading", { name: "Support cases are restricted" })).toBeInTheDocument();
  });

  it("restricts staff whose only support assignment has no tenant", async () => {
    loadPortalContext.mockResolvedValueOnce(portalContext({
      assignments: [assignment({ department: "finance", tenant_scope: "global" })],
    }));
    render(<SupportCaseWorkspace />);

    expect(await screen.findByRole("heading", { name: "Support cases are restricted" })).toBeInTheDocument();
  });

  it("shows staff their access and a truthful unprovisioned state without sample cases", async () => {
    render(<SupportCaseWorkspace />);

    expect(await screen.findByRole("heading", { level: 1, name: "Support cases" })).toBeInTheDocument();
    expect(screen.getByText("Visible — never shared with customers or providers")).toBeInTheDocument();
    expect(screen.getByText("This brand")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("The support case service isn’t available yet");
    expect(screen.getByRole("status")).toHaveTextContent("Nothing here is sample data.");
    expect(screen.getByRole("link", { name: "Back to support dashboard" })).toHaveAttribute("href", "/support");
    expect(screen.queryByRole("list", { name: "Case activity" })).not.toBeInTheDocument();
  });
});
