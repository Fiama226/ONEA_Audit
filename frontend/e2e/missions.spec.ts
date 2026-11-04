import { expect, test, type Page } from "@playwright/test";
import {
  E2E_AUDITEE_DIRECTION,
  E2E_MISSION_PREFIX,
  E2E_MISSION_PROCESS_LABEL,
  E2E_MISSION_PROCESS_CODE,
  ensureValidatedRiskMap,
} from "./api";
import { ApiSession, BASE, logIn, sessionOf } from "./session";

// Full-stack journey of the mission lifecycle (lot 3) on a throw-away database (scripts/e2e.sh): the RAI creates,
// staffs, plans, launches and issues the mission order; the lead auditor confirms the
// independence declaration and works steps II and IV; the auditee sees only their scope.
// Test data: missions titled "E2E <run id> — ..." (no cleanup: the database is discarded).
const TITLE = `${E2E_MISSION_PREFIX}Audit de la gestion des achats`;
const REFERENCE = /DAI\/\d{4}\/M\d{2,}/;

async function openMenuAction(page: Page, action: string) {
  await page.getByRole("button", { name: "Actions sur la mission" }).click();
  await page.getByRole("menuitem", { name: action }).click();
}

async function openStep(page: Page, numero: string) {
  await page
    .getByRole("navigation", { name: "Étapes de la mission" })
    .getByRole("link", { name: new RegExp(`^${numero}\\b`) })
    .click();
}

/** The status badge of one stepper entry. */
function stepStatus(page: Page, numero: string) {
  return page
    .getByRole("navigation", { name: "Étapes de la mission" })
    .getByRole("link", { name: new RegExp(`^${numero}\\b`) });
}

let missionUrl = "";

test.describe.configure({ mode: "serial" });

test.beforeAll(async () => {
  const rai = await ApiSession.login("rai");
  try {
    await ensureValidatedRiskMap(rai);
  } finally {
    await rai.dispose();
  }
});

test("RAI creates the mission, staffs it, plans it, launches it and issues the order", async ({
  page,
}) => {
  await logIn(page, "rai");

  await test.step("create the draft mission", async () => {
    await page
      .getByRole("navigation", { name: "Menu principal" })
      .getByRole("link", { name: "Missions" })
      .click();
    await page.getByRole("link", { name: "Créer une mission" }).first().click();
    await page.getByLabel("Titre", { exact: true }).fill(TITLE);
    await page.getByLabel("Type de mission").selectOption({ label: "Assurance" });
    await page
      .getByRole("checkbox", { name: new RegExp(`^${E2E_MISSION_PROCESS_CODE} - `) })
      .click();
    await page.getByRole("checkbox", { name: new RegExp(`^${E2E_AUDITEE_DIRECTION} - `) }).click();
    await page.getByLabel("Début prévu").fill("2026-11-02");
    await page.getByLabel("Fin prévue").fill("2026-12-18");
    await page.getByLabel("Budget (jours)").fill("20");
    await page
      .getByRole("textbox", { name: "Objectifs", exact: true })
      .fill("Évaluer la maîtrise du processus achats.");
    await page
      .getByRole("textbox", { name: "Périmètre", exact: true })
      .fill("Achats de fournitures et de travaux, exercice 2026.");
    await page.getByRole("button", { name: "Enregistrer" }).click();
    await expect(page.getByRole("heading", { name: TITLE, level: 1 })).toBeVisible();
    await expect(page.getByText("Brouillon").first()).toBeVisible();
    missionUrl = page
      .url()
      .replace(BASE, "")
      .replace(/\/etapes\/\d+$/, "");
  });

  await test.step("assign auditeur1 as lead and audite1 as auditee", async () => {
    await page
      .getByRole("navigation", { name: "Sections de la mission" })
      .getByRole("link", { name: "Équipe" })
      .click();
    await page.getByRole("button", { name: "Affecter une personne" }).click();
    let dialog = page.getByRole("alertdialog");
    await dialog.getByLabel("Rôle dans la mission").selectOption({ label: "Chef de mission" });
    await dialog.getByRole("radio", { name: /Auditeur1 E2E/ }).check();
    await dialog.getByRole("button", { name: "Affecter", exact: true }).click();
    await expect(dialog).toHaveCount(0);
    await expect(page.getByRole("cell", { name: "Chef de mission", exact: true })).toBeVisible();

    await page.getByRole("button", { name: "Affecter une personne" }).click();
    dialog = page.getByRole("alertdialog");
    await dialog.getByLabel("Rôle dans la mission").selectOption({ label: "Audité" });
    // The auditees of the mission's entity (direction DEX) are proposed and pre-checked.
    await expect(dialog.getByRole("checkbox", { name: /Audite1 E2E/ })).toBeChecked();
    await dialog.getByRole("button", { name: "Affecter", exact: true }).click();
    await expect(dialog).toHaveCount(0);
    await expect(page.getByRole("cell", { name: "Audité", exact: true })).toBeVisible();
  });

  await test.step("plan the mission: the reference DAI/AAAA/Mnn is displayed", async () => {
    await openMenuAction(page, "Planifier la mission");
    await page
      .getByRole("alertdialog")
      .getByRole("button", { name: "Planifier", exact: true })
      .click();
    await expect(page.getByText(REFERENCE).first()).toBeVisible();
    await expect(page.getByText("Planifiée").first()).toBeVisible();
  });

  await test.step("launch the mission", async () => {
    await openMenuAction(page, "Lancer la mission");
    await page
      .getByRole("alertdialog")
      .getByRole("button", { name: "Lancer", exact: true })
      .click();
    await expect(page.getByText("En planification").first()).toBeVisible();
  });

  await test.step("issue the mission order through the confirmation dialog: step I is done", async () => {
    await page.goto(`${missionUrl}/etapes/1`);
    await page.getByRole("button", { name: "Émettre l'ordre de mission" }).click();
    const dialog = page.getByRole("alertdialog");
    await expect(dialog).toContainText("Je soussigné(e)");
    await dialog.getByRole("checkbox", { name: "Je confirme" }).click();
    await dialog.getByRole("button", { name: "Émettre l'ordre", exact: true }).click();
    await expect(page.getByText(/Ordre de mission émis le/)).toBeVisible();
    await expect(page.getByText(/Empreinte : /)).toBeVisible();
    await expect(stepStatus(page, "I")).toContainText("Terminée");
  });
});

test("auditeur1 confirms the declaration, then completes steps II and IV", async ({ browser }) => {
  const page = await sessionOf(browser, "auditeur1");
  await page.goto(`${missionUrl}/etapes/2`);
  await expect(page.getByRole("heading", { name: TITLE, level: 1 })).toBeVisible();

  await test.step("confirm the independence declaration", async () => {
    await expect(
      page.getByText("Confirmez votre déclaration d'indépendance pour contribuer à la mission."),
    ).toBeVisible();
    await page.getByRole("button", { name: "Confirmer ma déclaration" }).click();
    const dialog = page.getByRole("alertdialog");
    await dialog.getByRole("radio", { name: "Je confirme cette déclaration" }).check();
    await dialog.getByRole("button", { name: "Confirmer la déclaration" }).click();
    await expect(dialog).toContainText(/Déclaration confirmée le/);
    await dialog.getByRole("button", { name: "Fermer" }).click();
    await expect(
      page.getByText("Confirmez votre déclaration d'indépendance pour contribuer à la mission."),
    ).toHaveCount(0);
  });

  await test.step("step II: start, plan and hold the opening meeting, plan an interview", async () => {
    await page.getByRole("button", { name: "Commencer l'étape" }).click();
    await expect(stepStatus(page, "II")).toContainText("En cours");

    const meeting = page.getByRole("region", { name: "Réunion d'ouverture" });
    await meeting.getByRole("button", { name: "Planifier la réunion" }).click();
    let dialog = page.getByRole("dialog");
    await dialog.getByLabel("Date et heure").fill("2026-11-04T09:00");
    await dialog.getByLabel("Lieu").fill("Salle de réunion DAI");
    await dialog.getByLabel("Compte rendu").fill("Présentation de la mission et du calendrier.");
    await dialog.getByRole("button", { name: "Enregistrer" }).click();
    await expect(dialog).toHaveCount(0);
    await meeting.getByRole("button", { name: "Marquer comme tenue" }).click();
    await page
      .getByRole("alertdialog")
      .getByRole("button", { name: "Marquer comme tenue" })
      .click();
    await expect(meeting.getByText(/Tenue le/)).toBeVisible();

    await page.getByRole("button", { name: "Planifier un entretien" }).click();
    dialog = page.getByRole("dialog");
    await dialog.getByLabel("Objet").fill("Entretien avec le directeur des achats");
    await dialog.getByLabel("Date et heure").fill("2026-11-06T10:00");
    await dialog.getByRole("checkbox", { name: /Auditeur1 E2E/ }).click();
    await dialog.getByRole("button", { name: "Enregistrer" }).click();
    await expect(dialog).toHaveCount(0);
    await expect(page.getByText("Entretien avec le directeur des achats")).toBeVisible();
  });

  await test.step("step II: complete", async () => {
    await page.getByRole("button", { name: "Terminer l'étape" }).click();
    await expect(stepStatus(page, "II")).toContainText("Terminée");
  });

  await test.step("step IV: add a new risk P 3 x I 5, the matrix cell shows 1, complete", async () => {
    await openStep(page, "IV");
    await page.getByRole("button", { name: "Commencer l'étape" }).click();
    await expect(stepStatus(page, "IV")).toContainText("En cours");

    await page.getByRole("button", { name: "Ajouter un risque nouveau" }).click();
    const dialog = page.getByRole("dialog");
    await dialog
      .getByLabel("Processus")
      .selectOption({ label: `${E2E_MISSION_PROCESS_CODE} — ${E2E_MISSION_PROCESS_LABEL}` });
    await dialog.getByLabel("Libellé du risque").fill("Fractionnement des marchés");
    await dialog.getByLabel("Probabilité", { exact: true }).selectOption("3");
    await dialog.getByLabel("Impact", { exact: true }).selectOption("5");
    await dialog.getByRole("button", { name: "Enregistrer" }).click();
    await expect(dialog).toHaveCount(0);

    const cell = page.getByRole("button", { name: /Probabilité 3, impact 5 : 1 risque/ });
    await expect(cell).toHaveText("1");
    await page.getByRole("button", { name: "Terminer l'étape" }).click();
    await expect(stepStatus(page, "IV")).toContainText("Terminée");
  });

  await test.step("the tracking sheet shows I, II and IV as completed", async () => {
    await page
      .getByRole("navigation", { name: "Sections de la mission" })
      .getByRole("link", { name: "Fiche de suivi" })
      .click();
    const table = page.getByRole("table", { name: "Suivi des étapes par phase" });
    for (const numero of ["I", "II", "IV"]) {
      await expect(table.getByRole("row", { name: new RegExp(`^${numero}\\b`) })).toContainText(
        "Terminée",
      );
    }
  });
  await page.context().close();
});

test("audite1 sees the mission and the opening meeting but not the Steps tab", async ({
  browser,
}) => {
  const page = await sessionOf(browser, "audite1");
  await page
    .getByRole("navigation", { name: "Menu principal" })
    .getByRole("link", { name: "Missions" })
    .click();
  await page.getByRole("link", { name: TITLE }).click();
  await expect(page.getByRole("heading", { name: TITLE, level: 1 })).toBeVisible();
  const tabs = page.getByRole("navigation", { name: "Sections de la mission" });
  await expect(tabs.getByRole("link", { name: "Réunions" })).toBeVisible();
  await expect(tabs.getByRole("link", { name: "Étapes" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Réunion d'ouverture" })).toContainText(
    "Salle de réunion DAI",
  );
  await page.context().close();
});
