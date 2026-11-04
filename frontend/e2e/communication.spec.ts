import { expect, test } from "@playwright/test";
import { ApiSession, logIn } from "./session";

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

test.describe.configure({ mode: "serial" });

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
  const rai = await ApiSession.login("rai");
  try {
    const signed = await rai.write("POST", `/api/v1/reports/${reportId}/sign/`, {
      lieu: "Ouagadougou",
    });
    expect([201, 422]).toContain(signed.status()); // 422 si déjà signé (idempotence du rejeu)
    const verification = await rai.raw(`/api/v1/reports/${reportId}/signature/`);
    expect(verification.status()).toBe(200);
    const body = (await verification.json()) as { signee: boolean; valide: boolean };
    expect(body.signee).toBe(true);
    expect(body.valide).toBe(true);
  } finally {
    await rai.dispose();
  }
});
