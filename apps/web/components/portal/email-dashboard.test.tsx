import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Department, PortalContext } from "@breero/types";
import AdminDashboard from "@/app/admin/page";
import ProviderDashboard from "@/app/provider/page";

const { loadPortalContext } = vi.hoisted(() => ({
  loadPortalContext: vi.fn<() => Promise<PortalContext>>(),
}));

vi.mock("@/lib/portal", () => ({
  loadPortalContext,
  canAccessDepartment: (context: PortalContext, department: Department) => context.departments.includes(department),
}));
vi.mock("./access-assignment-form", () => ({
  AccessAssignmentForm: () => <div data-testid="access-assignment-form" />,
}));

beforeEach(() => loadPortalContext.mockReset());

describe("email dashboard integration", () => {
  it.each([
    ["admin", "administration", true],
    ["admin", "administration", false],
    ["provider", "provider", true],
    ["provider", "provider", false],
  ] as const)("preserves the %s dashboard with email permission %s/%s", async (role, department, canCompose) => {
    loadPortalContext.mockResolvedValue({
      user: { full_name: "Synthetic User" },
      dashboard_path: `/${role}`,
      departments: [department],
      permissions: canCompose ? ["email.message.compose"] : [],
      identity_mode: "keycloak",
    } as unknown as PortalContext);
    render(role === "admin" ? <AdminDashboard /> : <ProviderDashboard />);
    const heading = await screen.findByRole("heading", { name: "Email provisioning & compose" });
    const card = within(heading.parentElement!);
    if (canCompose) {
      expect(card.getByRole("link", { name: "Open module" })).toHaveAttribute("href", `/${role}/email`);
    } else {
      expect(card.queryByRole("link", { name: "Open module" })).not.toBeInTheDocument();
      expect(card.getByRole("button", { name: "Access required" })).toBeDisabled();
    }
    expect(screen.getByLabelText("Search modules")).toBeInTheDocument();
    if (role === "admin") expect(screen.getByTestId("access-assignment-form")).toBeInTheDocument();
  });
});
