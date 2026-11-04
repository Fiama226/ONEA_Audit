import { expect, request, test, type Page } from "@playwright/test";
import { BASE, E2E_PASSWORD, logIn } from "./session";

// Connexion par le formulaire /connexion (identifiant + mot de passe) avec les comptes créés par
// `manage.py creer_comptes_e2e` (scripts/e2e.sh) : mot de passe connu, aucun changement forcé.
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

test("a delegate sees the account administration, a plain auditor does not", async ({ page }) => {
  await logIn(page, "auditeur1");
  const nav = page.getByRole("navigation", { name: "Menu principal" });
  await expect(nav.getByRole("link", { name: "Administration" })).toHaveCount(0);
  await page.goto("/administration/utilisateurs");
  // Attendre la vue « accès refusé » avant le contrôle négatif : sinon il passerait trop tôt.
  await expect(page.locator("main h1")).toHaveText("Accès refusé");
  await expect(page.getByRole("heading", { level: 1, name: "Utilisateurs" })).toHaveCount(0);
  await page.context().clearCookies();

  await logIn(page, "delegue1");
  await expect(nav.getByRole("link", { name: "Administration" })).toBeVisible();
  await page.goto("/administration/utilisateurs");
  await expect(page.getByRole("heading", { level: 1, name: "Utilisateurs" })).toBeVisible();
});

// Identifiant inexistant : aucun compte e2e ne peut être verrouillé par ce test (réponse identique).
test("a wrong password shows one neutral message and stays on the form", async ({ page }) => {
  await page.goto("/connexion");
  await page.getByLabel("Identifiant ou courriel professionnel").fill("inconnu.e2e");
  await page.getByLabel("Mot de passe", { exact: true }).fill(`${E2E_PASSWORD}-faux`);
  await page.getByRole("button", { name: "Se connecter" }).click();
  await expect(page.getByText("Identifiant ou mot de passe incorrect.")).toBeVisible();
  await expect(page).toHaveURL(/\/connexion$/);
});

test("the login page links to the forgotten-password page", async ({ page }) => {
  await page.goto("/connexion");
  await page.getByRole("link", { name: "Mot de passe oublié ?" }).click();
  await expect(page).toHaveURL(/\/mot-de-passe-oublie$/);
  await expect(page.getByRole("heading", { level: 1, name: "Mot de passe oublié" })).toBeVisible();
  await page.getByRole("link", { name: "Retour à la connexion" }).click();
  await expect(page).toHaveURL(/\/connexion$/);
});

test("a signed-in user reaches Mon compte and the password change page", async ({ page }) => {
  await logIn(page, "rai");
  await page.goto("/mon-compte");
  await expect(page.getByRole("heading", { level: 1, name: "Mon compte" })).toBeVisible();
  await page.goto("/mot-de-passe/changer");
  await expect(
    page.getByRole("heading", { level: 1, name: "Changer le mot de passe" }),
  ).toBeVisible();
});

test("a signed-in user can log out and is asked to sign in again", async ({ page }) => {
  await logIn(page, "rai");
  // Cookies de la session courante (dont le cookie HttpOnly), pour prouver qu'ils sont invalidés.
  const cookies = await page.context().cookies();
  // Une page protégée de plus dans l'historique : « Précédent » y reviendra après la déconnexion.
  await page.goto("/missions");
  await expect(page.getByRole("navigation", { name: "Menu principal" })).toBeVisible();
  await page.getByRole("button", { name: /Menu utilisateur/ }).click();
  await page.getByRole("menuitem", { name: "Se déconnecter" }).click();
  // (1) page de connexion affichée
  await expect(page).toHaveURL(/\/connexion$/);
  await expect(page.getByRole("button", { name: "Se connecter" })).toBeVisible();
  // (4) le bouton Précédent revient sur une page protégée vue connecté (le tableau de bord,
  // avant /missions) : aucun contenu protégé, retour à la connexion
  await page.goBack();
  await expect(page).toHaveURL(/\/connexion$/);
  await expect(page.getByRole("heading", { name: "Pilotage de l'audit interne" })).toHaveCount(0);
  await expect(page.getByRole("navigation", { name: "Menu principal" })).toHaveCount(0);
  // (2) une page protégée renvoie vers la connexion
  await page.goto("/missions");
  await expect(page.getByRole("button", { name: "Se connecter" })).toBeVisible();
  // (3) l'ancien cookie de session n'ouvre plus l'API (la session est détruite côté serveur)
  const ancienne = await request.newContext({
    baseURL: BASE,
    storageState: { cookies, origins: [] },
  });
  expect((await ancienne.get("/api/v1/me/")).status()).toBe(401);
  await ancienne.dispose();
});
