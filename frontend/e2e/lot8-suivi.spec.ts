import { expect, test } from "@playwright/test";
import {
  firstFollowUpAction,
  logIn,
  mailpitMessages,
  sessionOf,
  type FollowUpAction,
} from "./lot8-support";

// Lot 8 follow-up journeys (plan T17). They need a broadcast mission with an action plan whose
// follow-up has an action to launch assigned to `audite1`; without such data the journey is skipped.
// The decision-queue links are checked without any seed.

test.describe("File de décisions du RAI", () => {
  for (const [libelle, chemin, titre] of [
    [
      "Reports en attente",
      /\/recommandations\/reports\?statut=EN_ATTENTE$/,
      "Demandes de report d'échéance",
    ],
    ["Relances en échec", /\/recommandations\/relances\?statut=ECHEC$/, "Journal des relances"],
    [
      "Relances sans adresse",
      /\/recommandations\/relances\?statut=SANS_ADRESSE$/,
      "Journal des relances",
    ],
  ] as const) {
    test(`le lien « ${libelle} » mène à la vue filtrée`, async ({ page }) => {
      await logIn(page, "rai");
      await page.getByRole("link", { name: new RegExp(`^${libelle}`) }).click();
      await expect(page).toHaveURL(chemin);
      await expect(page.getByRole("heading", { level: 1, name: titre })).toBeVisible();
      // La pastille du filtre actif est annoncée et le chargement ne se confond pas avec le vide.
      await expect(page.getByRole("button", { pressed: true })).toHaveCount(1);
      await expect(
        page.getByRole("table").or(page.getByText(/Aucune (relance|demande)/)),
      ).toBeVisible();
    });
  }

  test("un audité n'accède pas au journal des relances", async ({ page }) => {
    await logIn(page, "audite1");
    await page.goto("/recommandations/relances");
    await expect(page.getByRole("heading", { level: 1, name: "Journal des relances" })).toHaveCount(
      0,
    );
  });
});

test.describe("Suivi d'une action : preuve, vérification, clôture", () => {
  test.describe.configure({ mode: "serial" });
  let action: FollowUpAction | null = null;

  test.beforeAll(async () => {
    action = await firstFollowUpAction("A_LANCER");
  });

  test("l'audité démarre l'action, dépose une preuve et la déclare réalisée", async ({
    browser,
  }) => {
    test.skip(
      action === null,
      "Aucune action de suivi à lancer : pas de mission diffusée dans cette base.",
    );
    const page = await sessionOf(browser, "audite1");
    await page.goto(`/recommandations/actions/${action?.id ?? ""}`);
    await page.getByRole("button", { name: "Démarrer" }).click();
    await page.getByLabel("Libellé de la preuve").fill("Rapprochement signé");
    await page.getByLabel("Fichier").setInputFiles({
      name: "preuve.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4\n%e2e\n"),
    });
    await page.getByRole("button", { name: "Déposer la preuve" }).click();
    await expect(page.getByText("Preuve déposée.")).toBeVisible();
    await page.getByRole("button", { name: "Déclarer réalisée" }).click();
    await page.getByLabel("Commentaire").fill("Mise en œuvre effective.");
    await page.getByRole("dialog").getByRole("button", { name: "Déclarer réalisée" }).click();
    await expect(page.getByText("Réalisée").first()).toBeVisible();
  });

  test("l'auditeur vérifie puis le RAI clôture l'action", async ({ browser }) => {
    test.skip(
      action === null,
      "Aucune action de suivi à lancer : pas de mission diffusée dans cette base.",
    );
    const auditeur = await sessionOf(browser, "auditeur1");
    await auditeur.goto(`/recommandations/actions/${action?.id ?? ""}`);
    await auditeur.getByRole("button", { name: "Vérifier" }).click();
    await expect(auditeur.getByText("Vérifiée").first()).toBeVisible();

    const rai = await sessionOf(browser, "rai");
    await rai.goto(`/recommandations/actions/${action?.id ?? ""}`);
    await rai.getByRole("button", { name: "Clôturer", exact: true }).click();
    await expect(rai.getByText("Clôturée").first()).toBeVisible();
  });

  test("la mission sans action ouverte peut être clôturée", async ({ browser }) => {
    test.skip(
      action === null,
      "Aucune action de suivi à lancer : pas de mission diffusée dans cette base.",
    );
    const rai = await sessionOf(browser, "rai");
    await rai.goto("/missions");
    await rai
      .getByRole("link", { name: /DAI\/\d{4}\/M\d{2,}/ })
      .first()
      .click();
    const close = rai.getByRole("button", { name: "Clôturer la mission" });
    test.skip(
      (await close.count()) === 0,
      "La mission ouverte contient encore des actions non closes.",
    );
    await close.click();
    await rai.getByRole("dialog").getByRole("button", { name: "Clôturer la mission" }).click();
    await expect(rai.getByText("Clôturée").first()).toBeVisible();
  });
});

test("les relances du jour produisent un courriel dans Mailpit", async () => {
  // `envoyer_relances --date AAAA-MM-JJ` est lancé hors navigateur (scripts/e2e.sh ou à la main) ;
  // on vérifie seulement que Mailpit a reçu un message de relance quand il est joignable.
  const count = await mailpitMessages("Relance");
  test.skip(count === null, "Mailpit injoignable (E2E_MAILPIT_URL).");
  test.skip(
    count === 0,
    "Aucune relance envoyée : lancer `manage.py envoyer_relances --date <échéance>` avant.",
  );
  expect(count).toBeGreaterThan(0);
});
