import { defineConfig, devices } from "@playwright/test";

// e2e runs against a throw-away database: `scripts/e2e.sh` (or e2e.ps1) creates it, starts the
// API (127.0.0.1:8010) and Vite (5174), runs Playwright, then drops everything. Needs the dev
// stack's Keycloak (realm "onea", client onea-frontend allowing http://localhost:5174/*).
// Variables: WEB_PORT (5174), E2E_API_URL (http://localhost:8000 when run by hand; the script
// sets http://localhost:8010), E2E_WEB_EXTERNAL=1 (the web server is already started by the
// script; otherwise Playwright starts Vite itself), E2E_RUN_ID (unique prefix of test data).
process.env.E2E_RUN_ID ??= String(Date.now());
const WEB_PORT = process.env.WEB_PORT ?? "5174";
const WEB_URL = `http://localhost:${WEB_PORT}`;
const API_URL = process.env.E2E_API_URL ?? "http://localhost:8000";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: WEB_URL,
    trace: "retain-on-failure",
    locale: "fr-FR",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: process.env.E2E_WEB_EXTERNAL
    ? undefined
    : {
        command: `npm run dev -- --port ${WEB_PORT}`,
        url: WEB_URL,
        // Same origin: the SPA calls /api on the Vite origin, Vite proxies it to Django.
        env: { VITE_API_URL: "", ONEA_API_URL: API_URL },
        reuseExistingServer: false,
        timeout: 120_000,
      },
});
