// The browser suite (M3 step 4): the page against a real `dipolar serve`, on Chromium, Firefox
// and WebKit. Each test starts its own server on a fresh project directory (e2e/harness.ts), so
// tests are independent and can run in parallel. Build the page first: `pnpm run build`.

import { defineConfig, devices } from "@playwright/test";

const viewport = { width: 1440, height: 900 };

export default defineConfig({
  testDir: "e2e",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: true,
  workers: process.env.CI ? 2 : 3,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: { trace: "retain-on-failure" },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"], viewport } },
    { name: "firefox", use: { ...devices["Desktop Firefox"], viewport } },
    { name: "webkit", use: { ...devices["Desktop Safari"], viewport } },
  ],
});
