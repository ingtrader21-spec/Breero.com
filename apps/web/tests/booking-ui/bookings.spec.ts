import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const booking = {
  id: "123e4567-e89b-42d3-a456-426614174000", reference: "BR-TEST-ONE",
  status: "CONFIRMED", total_amount: "120.00", currency: "USD",
  window_start: "2026-09-25T10:00:00Z", window_end: "2026-09-25T12:00:00Z", payment_required: false,
};
const capabilities = { request_intake: false, instant_booking: false, online_payments: false, automatic_assignment: false, provider_self_service: false, marketplace_matching: false, messaging: false, reviews: false };

test.beforeEach(async ({ page }) => {
  // No API request may leave this test's local fixture boundary.
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/public/capabilities")) return route.fulfill({ json: capabilities });
    if (path.endsWith("/customer/bookings")) return route.fulfill({ json: { items: [booking], total: 1, page: 1, page_size: 20 } });
    if (path.endsWith(`/customer/bookings/${booking.id}`)) return route.fulfill({ json: booking });
    return route.fulfill({ status: 404, json: { detail: "Not part of this UI fixture" } });
  });
});

for (const width of [320, 768, 1440]) {
  test(`booking list and detail are accessible at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/account/bookings");
    const link = page.getByRole("link", { name: "View booking BR-TEST-ONE" });
    await expect(link).toBeVisible();
    await link.focus();
    await expect(link).toBeFocused();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    let result = await new AxeBuilder({ page }).include(".account-content").withTags(["wcag2a", "wcag2aa"]).analyze();
    expect(result.violations).toEqual([]);
    await page.keyboard.press("Enter");
    await expect(page.getByText("Booking BR-TEST-ONE")).toBeVisible();
    await expect(page.getByRole("link", { name: /Back to bookings/ })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    result = await new AxeBuilder({ page }).include(".account-content").withTags(["wcag2a", "wcag2aa"]).analyze();
    expect(result.violations).toEqual([]);
  });
}

test("shows restricted access without records or a retry loop", async ({ page }) => {
  await page.route("**/customer/bookings?*", (route) => route.fulfill({ status: 403, json: { detail: "private diagnostic" } }));
  await page.goto("/account/bookings");
  await expect(page.getByRole("heading", { name: "Access restricted" })).toBeVisible();
  await expect(page.getByText("private diagnostic")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Try again" })).toHaveCount(0);
});

test("recovers from a service outage to an empty response", async ({ page }) => {
  let unavailable = true;
  await page.route("**/customer/bookings?*", (route) => unavailable
    ? route.fulfill({ status: 503, json: { detail: "Unavailable" } })
    : route.fulfill({ json: { items: [], total: 0, page: 1, page_size: 20 } }));
  await page.goto("/account/bookings");
  await expect(page.getByRole("heading", { name: "Connection interrupted" })).toBeVisible();
  unavailable = false;
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByRole("heading", { name: "No bookings here yet" })).toBeVisible();
});
