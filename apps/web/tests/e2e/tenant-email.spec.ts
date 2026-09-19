import { expect, test } from "@playwright/test";

test("login to tenant email provisioning, compose and durable outbox", async ({ page }) => {
  await page.goto("/login");
  await expect(page).toHaveURL(/\/account\/login$/);

  await page.getByLabel("Email address").fill("e2e-admin@breero.test");
  await page.getByLabel("Password").fill("E2E-admin-password-123!");
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page).toHaveURL(/\/admin$/);
  await expect(page.getByRole("heading", { name: "Administration dashboard" })).toBeVisible();
  await page.getByTestId("email-workspace-link").click();

  await expect(page).toHaveURL(/\/admin\/email$/);
  await expect(page.getByTestId("tenant-email-workspace")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Email provisioning & delivery" })).toBeVisible();
  await expect(page.locator('input[type="password"]')).toHaveCount(0);

  const domain = `mail-${Date.now()}.e2e.test`;
  await page.getByLabel("Sending domain").fill(domain);
  await page.getByLabel("DKIM selector").fill("breero");
  await page.getByRole("button", { name: "Add domain" }).click();
  await expect(page.getByText("Domain added. It must be independently verified before sending.")).toBeVisible();
  await expect(page.getByText(domain)).toBeVisible();
  await expect(page.getByText("PENDING", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Mark verified" }).click();
  await expect(page.getByText("Domain marked verified after trusted verification.")).toBeVisible();
  await expect(page.getByText("VERIFIED", { exact: true })).toBeVisible();

  await page.getByLabel("Verified domain").selectOption({ label: domain });
  await page.getByLabel("Local part").fill("operations");
  await page.getByLabel("Display name").fill("BREERO E2E Operations");
  await page.getByLabel("Reply-to").fill("reply@breero.test");
  await page.getByRole("button", { name: "Create sender" }).click();
  await expect(page.getByText("Sender created.")).toBeVisible();
  await expect(page.getByText("BREERO E2E Operations")).toBeVisible();

  await page.getByLabel("Credential label").fill("E2E SMTP");
  await page.getByLabel("SMTP host").fill("smtp.e2e.test");
  await page.getByLabel("Username").fill("e2e-smtp-user");
  await expect(page.getByLabel("Secret reference")).toHaveValue("breero-email/brand/breero/smtp/main");
  await page.getByRole("button", { name: "Save credential metadata" }).click();
  await expect(page.getByText("Credential metadata saved. Secret material remains outside the application database.")).toBeVisible();
  await expect(page.getByText("Secret reference configured")).toBeVisible();

  await page.getByLabel("Sender").selectOption({ label: "BREERO E2E Operations" });
  await page.getByLabel("Credential").selectOption({ label: "E2E SMTP" });
  await page.getByLabel("Recipient").fill("recipient@breero.test");
  await page.getByLabel("Subject").fill("BREERO tenant email E2E");
  await page.getByLabel("Message").fill("This message verifies the browser-to-client-to-outbox compose workflow.");
  await page.getByRole("button", { name: "Queue message" }).click();

  await expect(page.getByText("Message accepted by the backend and queued through the durable outbox.")).toBeVisible();
  await expect(page.getByTestId("email-outbox").getByText("PENDING_CONFIGURATION", { exact: true })).toBeVisible();
  await expect(page.getByTestId("email-outbox").getByText("Attempts: 0")).toBeVisible();
});
