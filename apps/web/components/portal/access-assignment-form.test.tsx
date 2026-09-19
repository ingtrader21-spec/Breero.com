import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AccessCatalog, PortalContext } from "@breero/types";
import { AccessAssignmentForm } from "./access-assignment-form";

const { loadPortalContext, accessCatalog, userAccess, replaceUserAccess } = vi.hoisted(() => ({
  loadPortalContext: vi.fn<() => Promise<PortalContext>>(),
  accessCatalog: vi.fn<() => Promise<AccessCatalog>>(),
  userAccess: vi.fn<() => Promise<PortalContext>>(),
  replaceUserAccess: vi.fn<() => Promise<PortalContext>>(),
}));

vi.mock("@/lib/portal", () => ({ loadPortalContext }));
vi.mock("@/lib/customer/api", () => ({
  customerApi: {
    auth: { accessCatalog, userAccess, replaceUserAccess },
  },
}));

const adminContext: PortalContext = {
  user: {
    id: "223e4567-e89b-42d3-a456-426614174000",
    email: "admin@breero.test",
    full_name: "Admin User",
    role: "admin",
    is_active: true,
    email_verified: true,
  },
  brand_key: "breero",
  dashboard_path: "/admin",
  roles: ["admin"],
  departments: ["administration"],
  permissions: ["admin.access.manage"],
  assignments: [{
    role: "admin",
    department: "administration",
    tenant_scope: "global",
    vendor_id: null,
    is_primary: true,
  }],
  identity_mode: "keycloak",
};

const targetContext: PortalContext = {
  user: {
    id: "123e4567-e89b-42d3-a456-426614174000",
    email: "support@breero.test",
    full_name: "Support User",
    role: "operations",
    is_active: true,
    email_verified: true,
  },
  brand_key: "breero",
  dashboard_path: "/support",
  roles: ["support"],
  departments: ["customer_support"],
  permissions: ["support.customers.read"],
  assignments: [{
    role: "support",
    department: "customer_support",
    tenant_scope: "brand",
    vendor_id: null,
    is_primary: true,
  }],
  identity_mode: "keycloak",
};

const catalog: AccessCatalog = {
  roles: ["support", "operations", "admin"],
  departments: ["customer_support", "dispatch", "administration"],
  tenant_scopes: ["global", "brand", "vendor"],
};

beforeEach(() => {
  loadPortalContext.mockReset();
  accessCatalog.mockReset();
  userAccess.mockReset();
  replaceUserAccess.mockReset();
  loadPortalContext.mockResolvedValue(adminContext);
  accessCatalog.mockResolvedValue(catalog);
  userAccess.mockResolvedValue(targetContext);
  replaceUserAccess.mockResolvedValue(targetContext);
});

describe("AccessAssignmentForm", () => {
  it("loads existing access before allowing review and confirmation", async () => {
    render(<AccessAssignmentForm />);

    expect(await screen.findByRole("heading", { name: "Department access" })).toBeInTheDocument();
    const userId = screen.getByRole("searchbox", { name: /User UUID/ });
    fireEvent.change(userId, { target: { value: targetContext.user.id } });
    expect(screen.getByRole("button", { name: "Review access changes" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Load existing access" }));

    expect(await screen.findByText("Support User")).toBeInTheDocument();
    expect(userAccess).toHaveBeenCalledWith(targetContext.user.id);
    expect(screen.getByRole("combobox", { name: /Role/ })).toHaveValue("support");
    expect(screen.getByRole("button", { name: "Review access changes" })).toBeEnabled();

    fireEvent.click(screen.getByRole("button", { name: "Review access changes" }));
    const drawer = screen.getByRole("dialog", { name: "Review access replacement" });
    expect(within(drawer).getByText(/support · customer_support · brand · primary/)).toBeInTheDocument();

    fireEvent.click(within(drawer).getByRole("button", { name: "Confirm access changes" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Access updated for support@breero.test");
    expect(replaceUserAccess).toHaveBeenCalledWith(
      targetContext.user.id,
      expect.objectContaining({
        brand_key: "breero",
        assignments: [expect.objectContaining({
          role: "support",
          department: "customer_support",
          tenant_scope: "brand",
          is_primary: true,
        })],
      }),
    );
  });

  it("reports lookup failures and keeps replacement disabled", async () => {
    userAccess.mockRejectedValueOnce(new Error("not found"));
    render(<AccessAssignmentForm />);

    await screen.findByRole("heading", { name: "Department access" });
    fireEvent.change(screen.getByRole("searchbox", { name: /User UUID/ }), { target: { value: targetContext.user.id } });
    fireEvent.click(screen.getByRole("button", { name: "Load existing access" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("We could not complete that request");
    expect(screen.getByRole("button", { name: "Review access changes" })).toBeDisabled();
  });
});
