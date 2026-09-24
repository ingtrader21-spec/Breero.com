import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// The mock API refuses to synthesize analytics, so these routes must render an
// honest error state instead of fabricated KPIs, at every supported width.
for (const path of ["/ops/analytics", "/provider/analytics"]) {
  test(`${path} never shows fabricated metrics without a projection`, async ({ page }) => {
    await page.goto(path);
    await expect(page.getByRole("alert").filter({ hasText: "We couldn’t load analytics" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
    await expect(page.getByText("Live", { exact: true })).toHaveCount(0);
    const results = await new AxeBuilder({ page }).disableRules(["color-contrast"]).analyze();
    expect(results.violations.filter((item) => ["serious", "critical"].includes(item.impact ?? ""))).toEqual([]);
  });
}

for (const width of [320, 768, 1440]) {
  test(`marketplace analytics has no horizontal overflow at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/ops/analytics");
    await expect(page.getByRole("heading", { name: "Marketplace analytics", level: 1 })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
    expect(overflow).toBe(false);
  });
}
