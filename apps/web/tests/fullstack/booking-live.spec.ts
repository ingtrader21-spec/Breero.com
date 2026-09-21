import { expect, test } from "@playwright/test";

const api = "http://127.0.0.1:28080/api/v1";

function nextWeekday(daysAhead: number): string {
  const value = new Date();
  value.setUTCDate(value.getUTCDate() + daysAhead);
  while (value.getUTCDay() === 0) value.setUTCDate(value.getUTCDate() + 1);
  return value.toISOString().slice(0, 10);
}

test("client booking, cookie session, logout and login persist the booking", async ({ page, browserName }) => {
  const email = `certification-client-${browserName}-${Date.now()}@breero.com`;
  const phone = `+1281${String(Date.now()).slice(-7)}`;
  const browserOffset = { chromium: 10, firefox: 11, webkit: 12 }[browserName] ?? 13;
  await page.goto("/booking");
  await page.locator('select[name="service_id"]').selectOption({ label: "Certification plumbing" });
  await page.getByLabel("Address line 1").fill("100 Main St");
  await page.getByLabel("City").fill("Houston");
  await page.getByLabel("State").fill("TX");
  await page.getByLabel("ZIP or ZIP+4").fill("77001");
  await page.getByLabel("Requested date").fill(nextWeekday(browserOffset));
  await page.getByRole("button", { name: "Check availability" }).click();
  await expect(page.getByText("Times shown in America/Chicago.")).toBeVisible();
  await page.getByRole("radio").first().check();
  await page.getByRole("button", { name: /hold this time/i }).click();
  await page.getByLabel("First name").fill("Live");
  await page.getByLabel("Last name").fill("Client");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Phone").fill(phone);
  await page.getByRole("button", { name: "Submit booking request" }).click();
  await expect(page.getByText(/pending manual[ -]dispatch/i)).toBeVisible();
  const cookies = await page.context().cookies();
  expect(cookies.find((item) => item.name === "breero_access")?.httpOnly).toBe(true);
  expect(cookies.find((item) => item.name === "breero_refresh")?.httpOnly).toBe(true);
  expect(await page.evaluate(() => Object.keys(sessionStorage).filter((key) => /token|session/i.test(key)))).toEqual([]);

  await page.evaluate(async ({ api }) => {
    const csrf = document.cookie.split("; ").find((item) => item.startsWith("breero_csrf="))?.split("=")[1] ?? "";
    const response = await fetch(`${api}/auth/browser/password/set`, {
      method: "POST", credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": decodeURIComponent(csrf) },
      body: JSON.stringify({ new_password: "Certification-client-2026" }),
    });
    if (!response.ok) throw new Error(await response.text());
  }, { api });
  await page.goto("/account/bookings");
  await expect(page.getByText(/pending manual[ -]dispatch/i).first()).toBeVisible();
  await page.getByRole("button", { name: "Log out" }).click();
  await page.waitForURL(/\/account\/login$/);
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password").fill("Certification-client-2026");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("link", { name: /continue to account/i }).click();
  await page.goto("/account/bookings");
  await expect(page.getByText(/pending manual[ -]dispatch/i).first()).toBeVisible();
});

test("provider cookie login exposes only its authorized dashboard data", async ({ page }) => {
  await page.goto("http://127.0.0.1:3201");
  await page.getByLabel("Email").fill("certification-provider@breero.com");
  await page.getByLabel("Password").fill("Certification-provider-2026");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Overview", level: 1 })).toBeVisible();
  await page.getByRole("button", { name: "Capacity" }).click();
  await expect(page.getByRole("heading", { name: "Capacity", level: 1 })).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
});

test("admin can inspect candidates, assign, and produce an audit event", async ({ page }) => {
  await page.goto("http://127.0.0.1:3202");
  await page.getByLabel("Email").fill("certification-admin@breero.com");
  await page.getByLabel("Password").fill("Certification-admin-2026");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Service catalog", level: 1 })).toBeVisible();
  const result = await page.evaluate(async ({ api }) => {
    const call = async (path: string, init?: RequestInit) => {
      const csrf = document.cookie.split("; ").find((item) => item.startsWith("breero_csrf="))?.split("=")[1] ?? "";
      const response = await fetch(`${api}${path}`, { ...init, credentials: "include", headers: { "Content-Type": "application/json", "X-CSRF-Token": decodeURIComponent(csrf), ...init?.headers } });
      if (!response.ok) throw new Error(await response.text());
      return response.json();
    };
    const bookings = await call("/admin/bookings");
    const pending = bookings.filter((item: { status: string }) => item.status === "PENDING_MANUAL_DISPATCH");
    let booking;
    let candidates = [];
    for (const item of pending) {
      const found = await call(`/admin/bookings/${item.id}/provider-candidates`);
      if (found.length) { booking = item; candidates = found; break; }
    }
    if (!booking) throw new Error("No assignable pending booking was found");
    const assigned = await call(`/admin/bookings/${booking.id}/assign`, { method: "POST", body: JSON.stringify({ professional_id: candidates[0].professional_id, reason: "Full-stack certification" }) });
    const audits = await call("/admin/audit-events");
    return { assigned: assigned.status, candidates: candidates.length, audited: audits.some((item: { action: string }) => item.action.includes("assign")) };
  }, { api });
  expect(result.candidates).toBeGreaterThan(0);
  expect(result.assigned).toBe("PROVIDER_ASSIGNED");
  expect(result.audited).toBe(true);
});
