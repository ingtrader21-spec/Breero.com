import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Button, Checkbox, DateSelector, Dialog, ErrorState, FormField, Input, Price, Tabs } from "./index";

describe("shared UI", () => {
  it("prevents disabled actions and permits the action when enabled", () => {
    let submissions = 0;
    const submit = () => { submissions += 1; };
    const view = render(<Button disabled onClick={submit}>Confirm request</Button>);
    const button = screen.getByRole("button", { name: "Confirm request" });
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(submissions).toBe(0);

    view.rerender(<Button onClick={submit}>Confirm request</Button>);
    expect(button).toBeEnabled();
    fireEvent.click(button);
    expect(submissions).toBe(1);
    view.unmount();
  });
  it("announces loading and disables the button", () => {
    render(<Button loading>Save</Button>);
    expect(screen.getByRole("button", { name: "Please wait" })).toBeDisabled();
    expect(screen.getByRole("button")).toHaveAttribute("aria-busy", "true");
  });

  it("connects form labels to controls", () => {
    render(<FormField label="Postcode" htmlFor="postcode"><Input id="postcode" /></FormField>);
    expect(screen.getByLabelText("Postcode")).toBeInTheDocument();
  });

  it("renders accessible selection controls", () => {
    render(<Checkbox label="Send updates" />);
    fireEvent.click(screen.getByText("Send updates"));
    expect(screen.getByRole("checkbox")).toBeChecked();
  });

  it("closes a dialog with Escape", () => {
    const onChange = vi.fn();
    render(<Dialog open onOpenChange={onChange} title="Confirm booking">Details</Dialog>);
    expect(screen.getByRole("dialog", { name: "Confirm booking" })).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onChange).toHaveBeenCalledWith(false);
  });

  it("formats prices for customers", () => {
    render(<Price amount={49} />);
    expect(screen.getByText("£49")).toBeInTheDocument();
  });

  it("exposes errors as alerts", () => {
    render(<ErrorState title="Unable to load" description="Try later" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Unable to load");
  });

  it("supports arrow-key navigation between tabs", () => {
    render(<Tabs tabs={[{ value: "one", label: "One", content: "First" }, { value: "two", label: "Two", content: "Second" }]} />);
    fireEvent.keyDown(screen.getByRole("tab", { name: "One" }), { key: "ArrowRight" });
    expect(screen.getByRole("tab", { name: "Two" })).toHaveAttribute("aria-selected", "true");
  });

  it("isolates multiple date selector groups", () => {
    const dates = [{ value: "today", day: "Mon", date: "11" }];
    render(<><DateSelector label="First dates" dates={dates} /><DateSelector label="Second dates" dates={dates} /></>);
    const radios = screen.getAllByRole("radio");
    expect(radios[0]).not.toHaveAttribute("name", radios[1].getAttribute("name"));
  });
});
