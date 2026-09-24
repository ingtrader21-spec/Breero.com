import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// The E2E mock API has no signed-in portal context, so the support case
// workspace must fail closed: a retryable error and no case content.
for (const width of [320, 768, 1440]) {
  test(`support cases fail closed without portal context at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/support/cases");
    const alert = page.getByRole("alert").filter({ hasText: "We couldn’t confirm your support access" });
    await expect(alert).toBeVisible();
    await expect(alert.getByRole("button", { name: "Try again" })).toBeVisible();
    await expect(page.getByText("Your case access")).toHaveCount(0);
    await expect(page.getByRole("list", { name: "Case activity" })).toHaveCount(0);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
    expect(overflow).toBe(false);
  });
}

test("support case error state has no serious automated accessibility violations", async ({ page }) => {
  await page.goto("/support/cases");
  await expect(page.getByRole("alert").filter({ hasText: "We couldn’t confirm your support access" })).toBeVisible();
  const results = await new AxeBuilder({ page }).disableRules(["color-contrast"]).analyze();
  expect(results.violations.filter((item) => ["serious", "critical"].includes(item.impact ?? ""))).toEqual([]);
});
