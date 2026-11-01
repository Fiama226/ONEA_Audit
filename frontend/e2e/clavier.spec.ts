import { expect, test, type Page } from "@playwright/test";
import { COMPTES } from "./inventaire";

// Audit clavier : lien d'évitement, ordre de tabulation, focus visible (style calculé), piège et
// retour du focus dans les dialogues, Échap, absence de piège clavier. Base peuplée (profil formation).
const PASSWORD = "onea2026";
const BASE = `http://localhost:${process.env.WEB_PORT ?? "5174"}`;
const STRICT = process.env.A11Y_STRICT === "1";

async function seConnecter(page: Page, compte: string) {
  await page.goto("/");
  await page.getByRole("button", { name: "Se connecter" }).click();
  await page.waitForURL(/\/realms\/onea\/protocol\/openid-connect\/auth/);
  await page.locator("#username").fill(compte);
  await page.locator("#password").fill(PASSWORD);
  await page.locator("#kc-login").click();
  await page.waitForURL(`${BASE}/`);
}

/** En mode rapport (A11Y_STRICT=0) un constat est consigné en annotation au lieu de faire échouer. */
function constat(
  condition: boolean,
  message: string,
  annotations: { type: string; description?: string }[],
) {
  if (condition) return;
  if (STRICT) throw new Error(message);
  annotations.push({ type: "constat-clavier", description: message });
}

/** Le focus est-il visible ? Contour (outline) ou ombre portée calculés non nuls sur l'élément actif. */
async function focusVisible(page: Page) {
  return page.evaluate(() => {
    const el = document.activeElement as HTMLElement | null;
    if (!el || el === document.body) return { ok: false, desc: "aucun élément actif" };
    const s = getComputedStyle(el);
    const contour = s.outlineStyle !== "none" && parseFloat(s.outlineWidth) > 0;
    const ombre = s.boxShadow !== "none" && s.boxShadow !== "";
    return {
      ok: contour || ombre,
      desc: `${el.tagName.toLowerCase()} ${(el.textContent ?? "").trim().slice(0, 30)}`,
    };
  });
}

test.beforeEach(async ({ page }) => {
  await seConnecter(page, COMPTES.RAI);
});

test("lien d'évitement : premier arrêt de tabulation, visible, amène au contenu", async ({
  page,
}, info) => {
  await page.keyboard.press("Tab");
  const lien = page.getByRole("link", { name: "Aller au contenu principal" });
  await expect(lien).toBeFocused();
  await expect(lien).toBeVisible();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/#contenu$/);
  constat(
    (await page.evaluate(() => document.activeElement?.id)) === "contenu",
    "Le focus n'atteint pas #contenu après le lien d'évitement",
    info.annotations,
  );
});

test("ordre de tabulation des actions principales et focus visible", async ({ page }, info) => {
  const vus: string[] = [];
  for (let i = 0; i < 25; i++) {
    await page.keyboard.press("Tab");
    const etat = await focusVisible(page);
    vus.push(etat.desc);
    constat(etat.ok, `Focus non visible sur : ${etat.desc}`, info.annotations);
  }
  // L'ordre suit le DOM : lien d'évitement, puis barre latérale, puis en-tête, puis contenu.
  expect(vus[0]).toContain("Aller au contenu principal");
  const iMenu = vus.findIndex((v) => /Tableau de bord/.test(v));
  expect(iMenu).toBeGreaterThan(0);
  await info.attach("ordre-tabulation", { body: vus.join("\n"), contentType: "text/plain" });
});

test("dialogues : piège du focus, Échap, retour du focus sur le déclencheur", async ({
  page,
}, info) => {
  await page.goto("/programme-annuel");
  const declencheur = page.getByRole("button", { name: /nouveau|créer/i }).first();
  await declencheur.focus();
  await declencheur.press("Enter");
  const dialogue = page.getByRole("dialog");
  await expect(dialogue).toBeVisible();

  // Piège : après N tabulations le focus reste dans le dialogue.
  for (let i = 0; i < 15; i++) {
    await page.keyboard.press("Tab");
    const dedans = await page.evaluate(() => !!document.activeElement?.closest('[role="dialog"]'));
    constat(dedans, `Le focus sort du dialogue à la tabulation ${i + 1}`, info.annotations);
  }
  await page.keyboard.press("Shift+Tab");
  await page.keyboard.press("Escape");
  await expect(dialogue).toBeHidden();
  const retour = await page.evaluate(() => document.activeElement?.textContent?.trim() ?? "");
  const attendu = ((await declencheur.textContent()) ?? "").trim();
  constat(
    retour === attendu,
    `Focus non rendu au déclencheur (« ${retour} » au lieu de « ${attendu} »)`,
    info.annotations,
  );
});

test("aucun piège clavier : on traverse la page puis on revient en arrière", async ({
  page,
}, info) => {
  await page.goto("/missions");
  await page.waitForLoadState("networkidle");
  const identifiants = new Set<string>();
  let boucle = false;
  for (let i = 0; i < 200; i++) {
    await page.keyboard.press("Tab");
    const cle = await page.evaluate(() => {
      const el = document.activeElement;
      return el
        ? `${el.tagName}|${el.id}|${el.getAttribute("aria-label") ?? ""}|${(el.textContent ?? "").trim().slice(0, 20)}`
        : "";
    });
    if (identifiants.has(cle) && cle.startsWith("BODY")) {
      boucle = true; // le focus a quitté le document (barre du navigateur) : pas de piège
      break;
    }
    identifiants.add(cle);
  }
  constat(
    identifiants.size > 5,
    "Moins de 6 éléments atteignables au clavier sur /missions",
    info.annotations,
  );
  // Retour arrière : Shift+Tab ne reste pas bloqué sur le même élément.
  const avant = await page.evaluate(() => document.activeElement?.outerHTML.slice(0, 80));
  await page.keyboard.press("Shift+Tab");
  const apres = await page.evaluate(() => document.activeElement?.outerHTML.slice(0, 80));
  constat(
    avant !== apres || boucle,
    "Shift+Tab ne déplace pas le focus (piège possible)",
    info.annotations,
  );
});
