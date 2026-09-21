import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

for (const path of ["/", "/services", "/services/plumbing", "/how-it-works", "/book", "/booking", "/login", "/account", "/about", "/contact", "/partners"]) {
  test(`${path} has no serious automated accessibility violations`, async ({ page }) => {
    await page.goto(path);
    if (path === "/book") await page.waitForURL("**/booking");
    await expect(page.locator("main")).toBeVisible();
    const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    expect(result.violations.filter((item) => ["serious", "critical"].includes(item.impact ?? ""))).toEqual([]);
  });
}
