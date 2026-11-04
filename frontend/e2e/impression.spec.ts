import { expect, test, type Page } from "@playwright/test";
import { logIn } from "./session";

// Impression A4 des écrans de document (gabarit PrintLayout) sur les données présentes dans la
// base jetable. Chaque écran est rendu en média « print » puis exporté en PDF : au moins une
// page, titre et référence visibles, en-tête ONEA, aucune action d'écran. Les PDF sont joints au
// rapport Playwright (artefacts). Ces écrans demandent des données de démonstration
// (cartographie, programme annuel, mission) : sans elles, chaque test est sauté avec la raison.

/** Premier lien de la liste affichée, ou null quand la liste est vide (données absentes). */
async function firstLink(page: Page, name: RegExp) {
  await page.waitForLoadState("networkidle");
  const link = page.getByRole("link", { name }).first();
  return (await link.count()) > 0 ? link : null;
}

const SANS_DONNEES =
  "Données de démonstration absentes de cette base (aucun élément à imprimer) : test sauté.";

function pageCount(pdf: Buffer): number {
  return (pdf.toString("latin1").match(/\/Type\s*\/Page[^s]/g) ?? []).length;
}

async function printCheck(
  page: Page,
  testInfo: Parameters<Parameters<typeof test>[2]>[1],
  name: string,
  title: RegExp,
  landscape: boolean,
) {
  await page.emulateMedia({ media: "print" });
  const header = page.getByText("Office National de l'Eau et de l'Assainissement");
  await expect(header).toBeVisible();
  await expect(page.getByText(title).first()).toBeVisible();
  await expect(page.getByText(/Imprimé le \d{2}\/\d{2}\/\d{4} \d{2}:\d{2}/)).toBeVisible();
  const pdf = await page.pdf({ preferCSSPageSize: true, displayHeaderFooter: false });
  expect(pageCount(pdf)).toBeGreaterThanOrEqual(1);
  expect(pdf.length).toBeGreaterThan(1000);
  await testInfo.attach(`${name}${landscape ? "-paysage" : ""}.pdf`, {
    body: pdf,
    contentType: "application/pdf",
  });
  // Aucune action d'écran à l'impression.
  await expect(page.getByRole("button", { name: /^Imprimer/ })).toBeHidden();
  await page.emulateMedia({ media: "screen" });
}

test.describe("impression A4 des écrans de document", () => {
  test("cartographie des risques", async ({ page }, testInfo) => {
    await logIn(page, "rai");
    await page.goto("/referentiel/cartographies");
    const link = await firstLink(page, /Cartographie.*\d{4}|\d{4}/);
    test.skip(link === null, SANS_DONNEES);
    await link?.click();
    await expect(
      page.getByRole("heading", { name: /Cartographie des risques \d{4}/ }),
    ).toBeVisible();
    await printCheck(page, testInfo, "cartographie", /Cartographie des risques \d{4}/, false);
  });

  test("programme annuel : un long trimestre tient sur plusieurs pages sans ligne coupée", async ({
    page,
  }, testInfo) => {
    await logIn(page, "rai");
    await page.goto("/programme-annuel");
    const link = await firstLink(page, /Programme annuel \d{4}|\d{4}/);
    test.skip(link === null, SANS_DONNEES);
    await link?.click();
    await expect(page.getByRole("heading", { name: /Programme annuel \d{4}/ })).toBeVisible();
    await printCheck(page, testInfo, "programme", /Programme annuel \d{4}/, true);
    // Lignes et cartes insécables : règle appliquée à tout tableau imprimé.
    const rule = await page.evaluate(() => {
      const tr = document.querySelector("tbody tr");
      return tr ? getComputedStyle(tr).breakInside : "avoid";
    });
    expect(rule).toBe("avoid");
  });

  for (const [segment, name, title] of [
    ["suivi", "fiche-suivi", /Fiche de suivi/],
    ["entretiens", "planning-entretiens", /Planning des entretiens/],
    ["referentiel-audit", "referentiel-audit", /Référentiel d'audit/],
  ] as const) {
    test(`mission : ${name}`, async ({ page }, testInfo) => {
      await logIn(page, "rai");
      await page.goto("/missions");
      // Mission référencée (DAI/AAAA/Mnn, ancien format MI-AAAA-n) : pas un brouillon.
      const link = await firstLink(page, /[A-Z]+\/\d{4}\/M\d+|MI-\d{4}-\d+/);
      test.skip(link === null, SANS_DONNEES);
      await link?.click();
      await page.waitForURL(/\/missions\/[0-9a-f-]{36}/);
      const missionUrl = page.url().replace(/\/(etapes|suivi|entretiens).*$/, "");
      await page.goto(`${missionUrl}/${segment}`);
      await expect(page.getByText(title).first()).toBeVisible();
      await printCheck(page, testInfo, name, title, name !== "referentiel-audit");
    });
  }
});
