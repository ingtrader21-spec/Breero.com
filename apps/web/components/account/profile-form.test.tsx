import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProfileForm } from "@/components/account/profile-form";

const { profile, updateProfile } = vi.hoisted(() => ({
  profile: vi.fn().mockResolvedValue({ id: "customer-1", email: "maya@example.com", full_name: "Maya Thompson", phone: "+44 7700 900123", email_verified: true }),
  updateProfile: vi.fn().mockResolvedValue({}),
}));
vi.mock("@/lib/customer/api", () => ({ customerApi: { customer: { profile, updateProfile } } }));

describe("ProfileForm", () => {
  it("replaces the loading state when the profile request completes", async () => {
    let resolveProfile!: (value: { id: string; email: string; full_name: string; phone: string; email_verified: boolean }) => void;
    profile.mockReturnValueOnce(new Promise((resolve) => { resolveProfile = resolve; }));
    render(<ProfileForm />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading your profile");
    expect(screen.queryByLabelText("Email")).not.toBeInTheDocument();

    await act(async () => {
      resolveProfile({ id: "customer-2", email: "ada@example.test", full_name: "Ada Lovelace", phone: "+44 7700 900456", email_verified: true });
    });

    expect(screen.queryByText("Loading your profile")).not.toBeInTheDocument();
    expect(screen.getByLabelText(/Full name/)).toHaveValue("Ada Lovelace");
    expect(screen.getByLabelText("Email")).toBeDisabled();
  });
  it("presents live customer details without allowing email edits", async () => {
    render(<ProfileForm/>);
    expect(await screen.findByLabelText("Email")).toBeDisabled();
    expect(screen.getByLabelText(/Full name/)).toHaveValue("Maya Thompson");
  });
  it("submits backend-supported profile fields", async () => {
    render(<ProfileForm/>);
    fireEvent.change(await screen.findByLabelText("Phone number"), { target: { value: "+44 7700 900999" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByRole("status")).toHaveTextContent("updated");
    expect(updateProfile).toHaveBeenCalledWith(expect.objectContaining({ phone: "+44 7700 900999", full_name: "Maya Thompson" }));
  });
});
