import { expect, test } from "@playwright/test";
import { logIn } from "./lot8-support";
import { ApiSession } from "./session";

// Lot 8 search journeys (plan T17). The index is filled by the API signals; a finding is looked up
// by a word of its title. Without a finding visible to the RAI the journeys are skipped.

type Finding = { id: string; titre: string; statut: string };

/** Findings visible to the RAI (session cookie), or `null` when the list cannot be read. */
async function listFindings(query: string): Promise<Finding[] | null> {
  const rai = await ApiSession.login("rai");
  try {
    const response = await rai.raw(`/api/v1/findings/?${query}`);
    if (!response.ok()) return null;
    return ((await response.json()) as { results: Finding[] }).results;
  } finally {
    await rai.dispose();
  }
}

async function someFinding(): Promise<Finding | null> {
  const body = await listFindings("page_size=50");
  return body?.find((f) => f.statut !== "BROUILLON") ?? null;
}

async function draftFinding(): Promise<Finding | null> {
  return (await listFindings("statut=BROUILLON&page_size=1"))?.[0] ?? null;
}

/** Longest word of a title: the most specific search term. */
function keyword(titre: string): string {
  return titre.split(/\s+/).reduce((a, b) => (b.length > a.length ? b : a), "");
}

test("le RAI trouve un constat par un mot de son titre", async ({ page }) => {
  const finding = await someFinding();
  test.skip(finding === null, "Aucun constat dans cette base.");
  await logIn(page, "rai");
  await page.goto(`/recherche?q=${encodeURIComponent(keyword(finding?.titre ?? ""))}`);
  await expect(
    page.getByRole("link", { name: new RegExp(keyword(finding?.titre ?? ""), "i") }).first(),
  ).toBeVisible();
});

test("un audité ne trouve pas un constat en brouillon", async ({ page }) => {
  const draft = await draftFinding();
  test.skip(draft === null, "Aucun constat en brouillon dans cette base.");
  const word = keyword(draft?.titre ?? "");
  await logIn(page, "audite1");
  await page.goto(`/recherche?q=${encodeURIComponent(word)}`);
  await expect(page.getByRole("heading", { level: 1, name: "Recherche" })).toBeVisible();
  // Attendre la fin de la requête : la liste est soit vide, soit sans le titre du brouillon.
  await expect(page.getByText(/Chargement|Recherche en cours/)).toHaveCount(0);
  await expect(page.getByRole("link", { name: draft?.titre ?? "" })).toHaveCount(0);
});

test("un auditeur non affecté ne trouve pas le constat d'une autre mission", async ({ page }) => {
  const finding = await someFinding();
  test.skip(finding === null, "Aucun constat dans cette base.");
  await logIn(page, "auditeur2");
  await page.goto(`/recherche?q=${encodeURIComponent(keyword(finding?.titre ?? ""))}`);
  await expect(page.getByRole("heading", { level: 1, name: "Recherche" })).toBeVisible();
  await expect(page.getByText(/Chargement|Recherche en cours/)).toHaveCount(0);
  await expect(page.getByRole("link", { name: finding?.titre ?? "" })).toHaveCount(0);
});
