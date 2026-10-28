import { readFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";
import { cleanupReferentiel, devToken } from "./api";

// Full-stack RAI flow of the Référentiel (lot 2) against the dev stack. Creates a process
// "ZZE" and two risk maps (2098, then its copy 2099), then removes everything (see api.ts).
const PASSWORD = "onea2026";
const BASE = "http://localhost:5173";
const PROCESS_LABEL = "Processus de test e2e";

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

async function addRisk(page: Page, libelle: string, probabilite: string, impact: string) {
  await page.getByRole("button", { name: "Ajouter un risque" }).click();
  // The map id travels in the path (not in a search param that a filter navigation could drop).
  await expect(page).toHaveURL(/\/referentiel\/cartographies\/[0-9a-f-]{36}\/risques\/nouveau$/);
  // Wait for the form page: the detail page has its own "Processus" filter.
  await expect(page.getByRole("heading", { name: "Nouveau risque", level: 2 })).toBeVisible();
  await page.getByLabel("Processus").selectOption({ label: `ZZE - ${PROCESS_LABEL}` });
  await page.getByLabel("Libellé du risque").fill(libelle);
  await page.getByLabel("Probabilité", { exact: true }).selectOption(probabilite);
  await page.getByLabel("Impact", { exact: true }).selectOption(impact);
  await page.getByRole("button", { name: "Enregistrer" }).click();
  // After creation the server-assigned code is displayed on the risk page.
  await expect(page.locator("output")).toHaveText(/^\d+-ZZE-R\d+$/);
  await page.getByRole("link", { name: "Retour à la cartographie" }).click();
}

async function createRiskMap(page: Page, annee: string, source?: string) {
  await page.getByRole("button", { name: "Créer une cartographie" }).first().click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Année").fill(annee);
  if (source) await dialog.getByLabel("Copier les risques de").selectOption({ label: source });
  await dialog.getByRole("button", { name: "Créer", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: `Cartographie des risques ${annee}` }),
  ).toBeVisible();
}

test.describe.configure({ mode: "serial" });

test.beforeAll(async () => {
  await cleanupReferentiel(await devToken("rai"));
});
test.afterAll(async () => {
  await cleanupReferentiel(await devToken("rai"));
});

test("RAI runs the whole risk-map lifecycle: create, matrix filter, validate, copy, compare, export", async ({
  page,
}) => {
  await logIn(page, "rai");
  const tabs = page.getByRole("navigation", { name: "Sections du référentiel" });

  await test.step("create the process ZZE", async () => {
    await page
      .getByRole("navigation", { name: "Menu principal" })
      .getByRole("link", { name: "Référentiel" })
      .click();
    await tabs.getByRole("link", { name: "Processus" }).click();
    await page.getByRole("link", { name: "Créer un processus" }).first().click();
    await page.getByLabel("Code").fill("ZZE");
    await page.getByLabel("Libellé").fill(PROCESS_LABEL);
    await page.getByLabel("Famille").selectOption({ label: "Support" });
    await page.getByRole("button", { name: "Enregistrer" }).click();
    await expect(page.getByRole("cell", { name: "ZZE", exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: PROCESS_LABEL })).toBeVisible();
  });

  await test.step("create the draft map 2098 and add two risks", async () => {
    await tabs.getByRole("link", { name: "Cartographies" }).click();
    await createRiskMap(page, "2098");
    await addRisk(page, "Risque de test e2e", "3", "5");
    await addRisk(page, "Risque mineur e2e", "1", "1");
    await expect(page.getByText("2 risques au total")).toBeVisible();
  });

  await test.step("clicking a matrix cell filters the risk list", async () => {
    const cell = page.getByRole("button", { name: /Probabilité 3, impact 5 : 1 risque/ });
    await expect(cell).toHaveText("1");
    await cell.click();
    const table = page.getByRole("table", { name: "Risques de la cartographie" });
    await expect(table.getByRole("link", { name: "1-ZZE-R1" })).toBeVisible();
    await expect(table.getByText("Élevé")).toBeVisible();
    await expect(table.getByRole("link", { name: "2-ZZE-R2" })).toHaveCount(0);
    await page.getByRole("button", { name: "Effacer le filtre" }).click();
    await expect(table.getByRole("link", { name: "2-ZZE-R2" })).toBeVisible();
  });

  await test.step("validate the map: confirmation dialog, then frozen state", async () => {
    await page.getByRole("button", { name: "Valider la cartographie" }).click();
    const dialog = page.getByRole("alertdialog");
    await expect(dialog).toContainText("la cartographie est figée");
    await dialog.getByRole("button", { name: "Valider définitivement" }).click();
    await expect(page.getByText(/Cartographie validée le/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Ajouter un risque" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Valider la cartographie" })).toHaveCount(0);
    // The risk page of a frozen map is read-only: no save, no delete.
    await page.getByRole("link", { name: "1-ZZE-R1" }).click();
    await expect(page.getByText(/Cartographie validée le/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Enregistrer" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Supprimer le risque" })).toHaveCount(0);
    await page.getByRole("link", { name: "Retour à la cartographie" }).click();
  });

  await test.step("export the validated map as CSV", async () => {
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: "Exporter en CSV" }).click();
    const file = await download;
    expect(file.suggestedFilename()).toMatch(/\.csv$/);
    const csv = readFileSync(await file.path(), "utf8");
    expect(csv.charCodeAt(0)).toBe(0xfeff);
    expect(csv).toContain("1-ZZE-R1");
    expect(csv).toContain("Risque de test e2e");
    expect(csv).toContain("2-ZZE-R2");
  });

  await test.step("copy 2098 into the draft 2099, edit it", async () => {
    await tabs.getByRole("link", { name: "Cartographies" }).click();
    await createRiskMap(page, "2099", "Cartographie des risques 2098");
    await expect(page.getByText("2 risques au total")).toBeVisible();
    // Impact 5 -> 4 on 1-ZZE-R1.
    await page.getByRole("link", { name: "1-ZZE-R1" }).click();
    await page.getByLabel("Impact", { exact: true }).selectOption("4");
    await page.getByRole("button", { name: "Enregistrer" }).click();
    await expect(page.getByText("Le risque a été enregistré.")).toBeVisible();
    await page.getByRole("link", { name: "Retour à la cartographie" }).click();
    // Delete 2-ZZE-R2.
    await page.getByRole("link", { name: "2-ZZE-R2" }).click();
    await page.getByRole("button", { name: "Supprimer le risque" }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Supprimer" }).click();
    await expect(page.getByText("1 risques au total")).toBeVisible();
    // Add a new risk: its number follows the deleted one (never reused).
    await addRisk(page, "Risque ajouté e2e", "2", "2");
  });

  await test.step("compare 2099 with 2098 (older is the reference, newer the target)", async () => {
    for (const from of ["2099", "2098"] as const) {
      const other = from === "2099" ? "2098" : "2099";
      if (from === "2098") {
        await page.getByRole("link", { name: "Retour à la cartographie" }).click();
        await page.goto("/referentiel/cartographies");
        await page.getByRole("link", { name: "2098", exact: true }).click();
      }
      await page.getByLabel("Comparer avec une autre version").selectOption({
        label: `Cartographie des risques ${other}`,
      });
      await page.getByRole("button", { name: "Comparer", exact: true }).click();
      await expect(
        page.getByText("De Cartographie des risques 2098 à Cartographie des risques 2099"),
      ).toBeVisible();
      const added = page.locator("section", {
        has: page.getByRole("heading", { name: /Risques ajoutés/ }),
      });
      await expect(added).toContainText("3-ZZE-R3");
      const removed = page.locator("section", {
        has: page.getByRole("heading", { name: /Risques retirés/ }),
      });
      await expect(removed).toContainText("2-ZZE-R2");
      const modified = page.getByRole("table").filter({ hasText: "1-ZZE-R1" });
      await expect(modified.getByRole("columnheader", { name: "Avant (2098)" })).toBeVisible();
      await expect(modified.getByRole("columnheader", { name: "Après (2099)" })).toBeVisible();
      const impactRow = modified.getByRole("row", { name: /Impact/ });
      const cells = await impactRow.getByRole("cell").allTextContents();
      expect(cells).toEqual(["5", "4"]);
    }
  });

  await test.step("the platform lists the maps and the process, which the cleanup then removes", async () => {
    await page.goto("/referentiel/cartographies");
    await expect(page.getByRole("link", { name: "2099", exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "2098", exact: true })).toBeVisible();
  });
});
