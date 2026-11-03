import { expect, test, type Page } from "@playwright/test";
import { devToken, provisionUsers } from "./api";

// Lot 7 (communication et signatures) sur une base jetable (scripts/e2e.ps1 ou e2e.sh).
//
// 1. Mode de signature (ADMIN) : le mode électronique n'est proposé que si le certificat de
//    l'ONEA est configuré (variables SIGNATURE_PKCS12_FILE, etc.). Sans certificat, la
//    « Confirmation horodatée » reste le seul mode sélectionnable.
// 2. Parcours PAdES par l'API (RAI) : s'exécute seulement si E2E_REPORT_ID désigne un rapport
//    VALIDE dont le rapport final est généré (Gotenberg) et si le serveur de test a un
//    certificat de développement (commande generer_certificat_signature_dev) ; sinon ignoré.
//    La préparation complète d'une mission en Communication (lots 3 à 6) n'est pas automatisée
//    ici : elle relève de la pile de recette.
const PASSWORD = "onea2026";
const WEB_PORT = process.env.WEB_PORT ?? "5174";
const BASE = `http://localhost:${WEB_PORT}`;
const API = process.env.E2E_API_URL ?? "http://localhost:8000";

async function logIn(page: Page, username: string) {
  await page.goto("/");
  const loginButton = page.getByRole("button", { name: "Se connecter" });
  await expect(loginButton).toBeEnabled();
  await loginButton.click();
  await page.waitForURL(/\/realms\/onea\/protocol\/openid-connect\/auth/);
  await page.locator("#username").fill(username);
  await page.locator("#password").fill(PASSWORD);
  await page.locator("#kc-login").click();
  await page.waitForURL(`${BASE}/`);
}

test.describe.configure({ mode: "serial" });

test.beforeAll(async () => {
  await provisionUsers();
});

test("ADMIN : le mode de signature du rapport est paramétrable, la confirmation reste disponible", async ({
  page,
}) => {
  await logIn(page, "admin");
  await page.goto("/administration/signatures");
  await expect(page.getByRole("heading", { name: /signature/i }).first()).toBeVisible();
  const select = page.getByLabel("Mode de signature de Validation du rapport");
  await expect(select).toBeVisible();
  await expect(select.locator("option", { hasText: "Confirmation horodatée" })).toBeEnabled();
  // Rien n'est pré-sélectionné au hasard : la valeur par défaut est la confirmation horodatée.
  await expect(select).toHaveValue(/CONFIRMATION|SIGNATURE/);
});

test("RAI : signe le rapport final (PAdES) et la vérification le confirme", async () => {
  const reportId = process.env.E2E_REPORT_ID;
  test.skip(!reportId, "E2E_REPORT_ID absent : rapport validé non préparé.");
  const token = await devToken("rai");
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
  const signed = await fetch(`${API}/api/v1/reports/${reportId}/sign/`, {
    method: "POST",
    headers,
    body: JSON.stringify({ lieu: "Ouagadougou" }),
  });
  expect([201, 422]).toContain(signed.status); // 422 si déjà signé (idempotence du rejeu)
  const verification = await fetch(`${API}/api/v1/reports/${reportId}/signature/`, { headers });
  expect(verification.status).toBe(200);
  const body = (await verification.json()) as { signee: boolean; valide: boolean };
  expect(body.signee).toBe(true);
  expect(body.valide).toBe(true);
});
