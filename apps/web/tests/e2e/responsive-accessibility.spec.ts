import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

for (const width of [320, 375, 390, 768, 1024, 1440]) {
  test(`booking remains usable at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/booking");
    await expect(page.getByRole("heading", { name: "Choose a time that works at your home." })).toBeVisible();
    await expect(page.getByRole("combobox", { name: "Service", exact: true })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
    expect(overflow).toBe(false);
  });
}

test("login has no serious automated accessibility violations", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: /sign in to breero/i })).toBeVisible();
  const results = await new AxeBuilder({ page }).disableRules(["color-contrast"]).analyze();
  expect(results.violations.filter((item) => ["serious", "critical"].includes(item.impact ?? ""))).toEqual([]);
});

test("provider application communicates pending onboarding", async ({ page }) => {
  await page.goto("/become-a-provider");
  await expect(page.getByRole("heading", { name: "Bring your service business to BREERO." })).toBeVisible();
  await expect(page.getByText(/pending provider organization/i)).toBeVisible();
});
