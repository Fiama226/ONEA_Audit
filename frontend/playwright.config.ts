import { defineConfig, devices } from "@playwright/test";

// e2e runs against the dev stack: Keycloak (dev realm "onea"), the Django API and the
// Vite dev server. `make up` starts the infrastructure; the web server below starts Vite.
// WEB_PORT (default 5173) lets a second stack run beside the dev one; the Keycloak client must
// allow the matching redirect URI (the dev realm only lists 5173, see docs/ e2e notes).
const WEB_PORT = process.env.WEB_PORT ?? "5173";
const WEB_URL = `http://localhost:${WEB_PORT}`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
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
  webServer: {
    command: `npm run dev -- --port ${WEB_PORT}`,
    url: WEB_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
