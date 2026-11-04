import { expect, test, type Page } from "@playwright/test";

// Keycloak dev realm "onea" (docker/keycloak/realm-onea.json) seeds
// the users rai / audite1 (password onea2026) and the public client onea-frontend
// (redirect http://localhost:5174/* for the e2e).
const PASSWORD = "onea2026";
const BASE = `http://localhost:${process.env.WEB_PORT ?? "5174"}`;
// Optional: full-page screenshots for visual review (frontend/e2e/screens/, git-ignored).
const SCREENS = process.env.E2E_SCREENSHOTS ? "e2e/screens" : null;

async function shot(page: Page, name: string) {
  if (!SCREENS) return;
  // The shell scrolls inside a fixed-height layout, so fullPage alone would clip it:
  // use a tall viewport for the capture.
  const original = page.viewportSize();
  await page.setViewportSize({ width: 1280, height: 1300 });
  await page.screenshot({ path: `${SCREENS}/${name}.png`, fullPage: true });
  if (original) await page.setViewportSize(original);
}

async function logIn(page: Page, username: string) {
  await page.goto("/");
  // Anonymous visitors land on /connexion, whose button starts the Keycloak code flow.
  const loginButton = page.getByRole("button", { name: "Se connecter" });
  await expect(loginButton).toBeEnabled();
  await loginButton.click();
  await page.waitForURL(/\/realms\/onea\/protocol\/openid-connect\/auth/);
  await page.locator("#username").fill(username);
  await page.locator("#password").fill(PASSWORD);
  await page.locator("#kc-login").click();
  await page.waitForURL(`${BASE}/`);
}

test("RAI signs in and sees the dashboard with the Référentiel entry", async ({ page }) => {
  await logIn(page, "rai");
  expect(page.url()).toBe(`${BASE}/`);
  await expect(page.getByRole("heading", { name: "Pilotage de l'audit interne" })).toBeVisible();
  const nav = page.getByRole("navigation", { name: "Menu principal" });
  await expect(nav.getByRole("link", { name: "Tableau de bord" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Référentiel" })).toBeVisible();
  await shot(page, "dashboard-rai");

  // Collapsed sidebar (labels move to tooltips, links keep their accessible names).
  await page.getByRole("button", { name: "Menu latéral" }).click();
  await expect(page.getByRole("button", { name: "Menu latéral" })).toHaveAttribute(
    "aria-expanded",
    "false",
  );
  await shot(page, "sidebar-collapsed");
});

test("AUDITE signs in and sees neither Référentiel nor Administration", async ({ page }) => {
  await logIn(page, "audite1");
  await expect(page.getByRole("heading", { name: "Mes constats et actions" })).toBeVisible();
  const nav = page.getByRole("navigation", { name: "Menu principal" });
  await expect(nav.getByRole("link", { name: "Tableau de bord" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Référentiel" })).toHaveCount(0);
  await expect(nav.getByRole("link", { name: "Administration" })).toHaveCount(0);
  await shot(page, "dashboard-audite");
});

test("a signed-in user can log out and is asked to sign in again", async ({ page }) => {
  await logIn(page, "rai");
  // Jeton d'accès courant, pour prouver plus bas qu'il ne donne plus accès.
  const ancienJeton = await page.evaluate(() => {
    for (const cle of Object.keys(sessionStorage)) {
      if (!cle.startsWith("oidc.user:")) continue;
      const brut = sessionStorage.getItem(cle);
      if (brut) return (JSON.parse(brut) as { access_token: string }).access_token;
    }
    return null;
  });
  expect(ancienJeton).toBeTruthy();
  await page.getByRole("button", { name: /Menu utilisateur/ }).click();
  await page.getByRole("menuitem", { name: "Se déconnecter" }).click();
  // Keycloak may ask for confirmation when no id_token_hint is sent.
  await page.waitForURL(
    (url) => url.origin === BASE || /\/protocol\/openid-connect\/logout/.test(url.pathname),
  );
  const confirm = page.locator("#kc-logout");
  if (await confirm.isVisible().catch(() => false)) {
    await confirm.click();
    await page.waitForURL((url) => url.origin === BASE);
  }
  // (1) page de connexion affichée
  await expect(page.getByRole("button", { name: "Se connecter" })).toBeVisible();
  // (2) aucun utilisateur OIDC dans sessionStorage
  const restes = await page.evaluate(() =>
    Object.keys(sessionStorage).filter((cle) => cle.startsWith("oidc.user:")),
  );
  expect(restes).toEqual([]);
  // (3) une page protégée renvoie vers la connexion
  await page.goto("/missions");
  await expect(page.getByRole("button", { name: "Se connecter" })).toBeVisible();
  // (4) l'ancien jeton d'accès n'ouvre plus l'API
  // Même origine : l'API est jointe via l'origine de Vite (baseURL), qui relaie /api.
  const reponse = await page.request.get("/api/v1/me/", {
    headers: { Authorization: `Bearer ${ancienJeton}` },
  });
  expect(reponse.status()).toBe(401);
  // (5) le bouton Précédent n'affiche aucun contenu protégé
  await page.goBack();
  await expect(page.getByRole("heading", { name: "Pilotage de l'audit interne" })).toHaveCount(0);
  await expect(page.getByRole("navigation", { name: "Menu principal" })).toHaveCount(0);
});
