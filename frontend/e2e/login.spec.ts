import { expect, test, type Page } from "@playwright/test";

// Dev stack only: the Keycloak dev realm "onea" (docker/keycloak/realm-onea.json) seeds
// the user rai / onea2026 and the public client onea-frontend (redirect http://localhost:5173/*).
const USERNAME = "rai";
const PASSWORD = "onea2026";

async function logIn(page: Page) {
  await page.goto("/");
  // Anonymous visitors land on /connexion first, then are sent to Keycloak.
  const loginButton = page.getByRole("button", { name: "Se connecter" });
  if (await loginButton.isVisible({ timeout: 5_000 }).catch(() => false)) {
    await loginButton.click();
  }
  await page.waitForURL(/\/realms\/onea\/protocol\/openid-connect\/auth/);
  await page.locator("#username").fill(USERNAME);
  await page.locator("#password").fill(PASSWORD);
  await page.locator("#kc-login").click();
  await page.waitForURL("http://localhost:5173/");
}

test("redirects to Keycloak, signs in as rai and returns to the application", async ({ page }) => {
  await logIn(page);
  expect(new URL(page.url()).pathname).toBe("/");
  // The application did not fall into the error page.
  await expect(page.getByText("Service indisponible")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Audit interne ONEA" })).toBeVisible();
});

// TODO(Task 9): enable once the application shell (dashboard + sidebar) is merged.
test.fixme("shows the dashboard and the Référentiel entry after login", async ({ page }) => {
  await logIn(page);
  await expect(page.getByText("Tableau de bord").first()).toBeVisible();
  await expect(page.getByRole("link", { name: "Référentiel" })).toBeVisible();
});
