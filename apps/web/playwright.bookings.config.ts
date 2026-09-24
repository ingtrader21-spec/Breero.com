import { defineConfig, devices } from "@playwright/test";

// Isolated UI contract tests: the real HTTP client runs against intercepted
// local requests. This is not evidence of authenticated backend integration.
export default defineConfig({
  testDir: "./tests/booking-ui",
  outputDir: "./test-results/booking-ui",
  workers: 1,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  use: { baseURL: "http://127.0.0.1:3133", trace: "retain-on-failure" },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "firefox", use: { ...devices["Desktop Firefox"] } },
    { name: "webkit", use: { ...devices["Desktop Safari"] } },
  ],
  webServer: {
    command: "pnpm build && pnpm exec next start -H 127.0.0.1 -p 3133",
    env: {
      NEXT_PUBLIC_API_MODE: "live",
      NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:3133/api/v1",
      // Permits a local URL in this test build; the real HTTP client still runs.
      NEXT_PUBLIC_E2E_ALLOW_MOCK: "1",
    },
    url: "http://127.0.0.1:3133", reuseExistingServer: false, timeout: 240_000,
  },
});
