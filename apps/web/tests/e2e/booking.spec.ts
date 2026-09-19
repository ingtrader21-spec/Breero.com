import { expect, test } from "@playwright/test";

const service = {
  id: "11111111-1111-1111-1111-111111111111",
  slug: "cleaning",
  name: "Cleaning",
  is_active: true,
  is_bookable: false,
};

const requestOnlyCapabilities = {
  request_intake: true,
  instant_booking: false,
  automatic_assignment: false,
  online_payments: false,
  payments: false,
  payouts: false,
  paid_leads: false,
  provider_self_service: false,
  marketplace_matching: false,
  messaging: false,
  reviews: false,
  marketing: false,
};

async function mockCapabilities(
  page: import("@playwright/test").Page,
  capabilities = requestOnlyCapabilities,
) {
  await page.route("**/api/capabilities", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(capabilities),
    }),
  );
}

async function mockCatalog(page: import("@playwright/test").Page) {
  await page.route("**/api/services", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([service]),
    }),
  );
}

for (const width of [375, 430, 768, 1024, 1280, 1440])
  test(`homepage and request-service entry fit ${width}px`, async ({ page }) => {
    await mockCapabilities(page);
    await mockCatalog(page);
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: /home services, without the hassle/i }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
      ),
    ).toBe(true);

    await page.goto("/booking?service=cleaning");
    await expect(page).toHaveURL(/\/booking\?service=cleaning$/);
    await expect(page.getByRole("heading", { name: /choose a time that works at your home/i })).toBeVisible();
    await expect(page.getByRole("button", { name: "Check availability" })).toBeEnabled();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  });

test("request-service submission remains pending manual dispatch", async ({ page }) => {
  await mockCapabilities(page);
  await mockCatalog(page);
  let submitted: Record<string, unknown> | undefined;
  let validated: Record<string, unknown> | undefined;
  await page.route("**/api/addresses/validate", async (route) => {
    validated = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        serviceable: true,
        formatted_address: "1600 Pennsylvania Avenue NW, Washington, DC 20500, US",
        address_id: "address-canary",
        service_area_id: "area-canary",
        legal_entity_code: "BREERO-US",
      }),
    });
  });
  await page.route("**/api/public-submissions/service-requests", async (route) => {
    submitted = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({
        status: "REQUESTED",
        dispatch_state: "PENDING_MANUAL_DISPATCH",
      }),
    });
  });

  await page.goto("/request-service?utm_source=canary&utm_campaign=request-only");
  await page.getByLabel("Name").fill("Owner Controlled Canary");
  await page
    .getByRole("textbox", { name: "Email", exact: true })
    .fill("owner-canary@example.test");
  await page.getByRole("textbox", { name: "Phone", exact: true }).fill("+12025550123");
  await page.getByRole("combobox", { name: "Service", exact: true }).selectOption("cleaning");
  await page.getByLabel("Street address").fill("1600 Pennsylvania Avenue NW");
  await page.getByLabel("City").fill("Washington");
  await page.getByLabel("State or district").selectOption("DC");
  await page.getByLabel("ZIP code").fill("20500");
  await page.getByLabel("Preferred date").fill("2026-09-01");
  await page.getByLabel("Preferred local time").fill("09:00");
  await page
    .getByLabel("What do you need help with?")
    .fill("Owner-controlled request test");
  await page.getByLabel(/may contact me about this request/i).check();
  await page.getByRole("button", { name: "Request service" }).click();

  await expect(
    page.getByText(/not an appointment, provider assignment, final price or payment confirmation/i),
  ).toBeVisible();
  expect(submitted).toMatchObject({
    name: "Owner Controlled Canary",
    service_slug: "cleaning",
    state: "DC",
    postal_code: "20500",
    utm_source: "canary",
    utm_campaign: "request-only",
    transactional_contact_allowed: true,
    marketing_consent: false,
    sms_consent: false,
    email_consent: false,
  });
  expect(submitted).not.toHaveProperty("paid");
  expect(submitted).not.toHaveProperty("provider_id");
  expect(submitted).not.toHaveProperty("appointment_status");
  expect(validated).toEqual({
    address: "1600 Pennsylvania Avenue NW, Washington, DC, 20500, US",
  });
});

test("catalog refresh failure uses the standard request catalog", async ({ page }) => {
  await mockCapabilities(page);
  await page.route("**/api/services", (route) => route.fulfill({ status: 503 }));
  await page.goto("/request-service");
  await expect(page.getByText(/standard service list is shown/i)).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Service", exact: true })).toContainText("Roofing");
  await expect(page.getByRole("button", { name: "Request service" })).toBeEnabled();
});

test("authoritative empty catalog keeps submission fail-closed", async ({ page }) => {
  await mockCapabilities(page);
  await page.route("**/api/services", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: "[]",
  }));
  await page.goto("/request-service");
  await expect(page.getByText(/no services are currently accepting requests/i)).toBeVisible();
  await expect(page.getByRole("button", { name: "Request service" })).toBeDisabled();
});

test("disabled request-intake capability keeps submission fail-closed", async ({ page }) => {
  await mockCapabilities(page, { ...requestOnlyCapabilities, request_intake: false });
  await mockCatalog(page);

  await page.goto("/request-service");

  await expect(page.getByLabel("Preferred date (request only)")).toBeVisible();
  await expect(page.getByRole("button", { name: "Request service" })).toBeDisabled();
});

test("unavailable capability authority keeps submission fail-closed", async ({ page }) => {
  await page.route("**/api/capabilities", (route) => route.fulfill({ status: 503 }));
  await mockCatalog(page);

  await page.goto("/request-service");

  await expect(page.getByLabel("Preferred date (request only)")).toBeVisible();
  await expect(page.getByRole("button", { name: "Request service" })).toBeDisabled();
});
