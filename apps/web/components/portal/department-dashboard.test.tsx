import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Department, PortalContext } from "@breero/types";
import { DepartmentDashboard } from "./department-dashboard";

const { loadPortalContext } = vi.hoisted(() => ({
  loadPortalContext: vi.fn<() => Promise<PortalContext>>(),
}));

vi.mock("@/lib/portal", () => ({
  loadPortalContext,
  canAccessDepartment: (context: PortalContext, department: Department) => context.departments.includes(department),
}));

const context: PortalContext = {
  user: {
    id: "123e4567-e89b-42d3-a456-426614174000",
    email: "operator@breero.test",
    full_name: "Operations User",
    role: "operations",
    is_active: true,
    email_verified: true,
  },
  brand_key: "breero",
  dashboard_path: "/ops",
  roles: ["operations"],
  departments: ["dispatch"],
  permissions: ["ops.dispatch.read", "ops.bookings.read"],
  assignments: [{
    role: "operations",
    department: "dispatch",
    tenant_scope: "brand",
    vendor_id: null,
    is_primary: true,
  }],
  identity_mode: "keycloak",
};

const modules = [
  {
    title: "Dispatch queue",
    description: "Requests awaiting operational handling.",
    permission: "ops.dispatch.read",
    href: "/ops/dispatch",
  },
  {
    title: "Bookings",
    description: "Operational booking visibility.",
    permission: "ops.bookings.read",
  },
  {
    title: "Audit",
    description: "Operational audit records.",
    permission: "ops.audit.read",
  },
];

function renderDashboard() {
  return render(
    <DepartmentDashboard
      department="dispatch"
      eyebrow="Operations"
      title="Operations dashboard"
      description="Authorized operational workspace."
      modules={modules}
    />,
  );
}

beforeEach(() => {
  loadPortalContext.mockReset();
  loadPortalContext.mockResolvedValue(context);
});

describe("DepartmentDashboard", () => {
  it("shows a named loading state while portal context is unresolved", () => {
    loadPortalContext.mockImplementationOnce(() => new Promise<PortalContext>(() => undefined));
    renderDashboard();

    expect(screen.getByRole("status")).toHaveTextContent("Loading your authorized workspace");
  });

  it("shows an error state and recovers through the retry button", async () => {
    loadPortalContext
      .mockRejectedValueOnce(new Error("portal unavailable"))
      .mockResolvedValueOnce(context);
    renderDashboard();

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByRole("heading", { name: "We couldn’t load your workspace" })).toBeInTheDocument();
    fireEvent.click(within(alert).getByRole("button", { name: "Try again" }));

    expect(await screen.findByRole("heading", { name: "Operations dashboard" })).toBeInTheDocument();
    expect(loadPortalContext).toHaveBeenCalledTimes(2);
  });

  it("supports search, state filters, module buttons and the detail drawer", async () => {
    renderDashboard();

    expect(await screen.findByRole("heading", { name: "Operations dashboard" })).toBeInTheDocument();
    expect(screen.getByText("2 available")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Search modules"), { target: { value: "audit" } });
    expect(screen.getByRole("heading", { name: "Audit" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Bookings" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Reset search and filters" }));
    fireEvent.change(screen.getByLabelText("Filter modules"), { target: { value: "restricted" } });
    expect(screen.getByRole("heading", { name: "Audit" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Dispatch queue" })).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Filter modules"), { target: { value: "all" } });
    fireEvent.click(screen.getByRole("button", { name: "View Dispatch queue details" }));

    const drawer = screen.getByRole("dialog", { name: "Dispatch queue" });
    expect(within(drawer).getByText("ops.dispatch.read")).toBeInTheDocument();
    expect(within(drawer).getByRole("link", { name: "Open module" })).toHaveAttribute("href", "/ops/dispatch");
    fireEvent.click(within(drawer).getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog", { name: "Dispatch queue" })).not.toBeInTheDocument();
  });

  it("shows a recoverable empty result state without fabricating dashboard data", async () => {
    renderDashboard();

    await screen.findByRole("heading", { name: "Operations dashboard" });
    fireEvent.change(screen.getByLabelText("Search modules"), { target: { value: "not-a-real-module" } });

    expect(screen.getByRole("heading", { name: "No modules match" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show all modules" }));
    expect(screen.getByRole("heading", { name: "Dispatch queue" })).toBeInTheDocument();
  });
});
