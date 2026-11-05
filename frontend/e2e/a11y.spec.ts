import { mkdirSync, writeFileSync } from "node:fs";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import {
  COMPTE_DELEGUE,
  COMPTES,
  DIALOGUES,
  PAGES_PUBLIQUES,
  ROUTES,
  type EntreeRoute,
  type Ressource,
  type RoleDemo,
} from "./inventaire";
import { ApiSession, logIn } from "./session";

// Audit axe (wcag2a, wcag2aa, wcag21aa) : pour chaque rôle et chaque route autorisée, page
// chargée puis dialogues principaux ouverts. À lancer par scripts/e2e.sh e2e/a11y.spec.ts
// (comptes créés par creer_comptes_e2e ; les routes sans données sont consignées « non résolues »).
// A11Y_STRICT=0 (défaut) : rapport JSON seul ; A11Y_STRICT=1 : échec sur serious/critical (T24, T25).
const STRICT = process.env.A11Y_STRICT === "1";
const TAGS = ["wcag2a", "wcag2aa", "wcag21aa"];
const SORTIE = "test-results/a11y-violations.json";

type Constat = {
  role: string;
  route: string;
  contexte: string;
  regle: string;
  gravite: string | null | undefined;
  element: string;
  aide: string;
};
const constats: Constat[] = [];
const nonResolues: string[] = [];

/** Liste API → premier identifiant (démo). Les chemins sont ceux du routeur DRF (urls.py des applications). */
const LISTES: Record<Ressource, (ctx: Record<string, string>) => string> = {
  mission: () => "/api/v1/missions/",
  plan: () => "/api/v1/audit-plans/",
  ligne: () => "/api/v1/audit-plan-lines/",
  cartographie: () => "/api/v1/risk-maps/",
  risque: () => "/api/v1/risks/",
  processus: () => "/api/v1/processes/",
  utilisateur: () => "/api/v1/user-accounts/",
  document: () => "/api/v1/documents/",
  gabarit: () => "/api/v1/document-types/",
  rapport: () => "/api/v1/reports/",
  action: () => "/api/v1/follow-up/actions/",
  constat: (c) => `/api/v1/findings/?mission=${c.mission ?? ""}`,
  fiche: (c) => `/api/v1/test-sheets/?mission=${c.mission ?? ""}`,
};

async function premier(api: ApiSession, ressource: Ressource, ctx: Record<string, string>) {
  const reponse = await api.raw(LISTES[ressource](ctx));
  if (!reponse.ok()) return null;
  const corps = (await reponse.json()) as { results?: { id?: string | number; code?: string }[] };
  const element = corps.results?.[0];
  // Les types de document/gabarit sont adressés par code, les autres par identifiant.
  return element
    ? String(ressource === "gabarit" ? (element.code ?? element.id) : element.id)
    : null;
}

async function resoudre(route: EntreeRoute, api: ApiSession): Promise<string | null> {
  const ctx: Record<string, string> = {};
  let chemin = route.motif;
  for (const [cle, valeur] of Object.entries(route.fixes ?? {}))
    chemin = chemin.replace(`:${cle}`, valeur);
  for (const ressource of route.parametres ?? []) {
    const id = await premier(api, ressource, ctx);
    if (!id) return null;
    ctx[ressource] = id;
    chemin = chemin.replace(/:[A-Za-z]+/, id); // les paramètres se remplissent dans l'ordre
  }
  return chemin;
}

async function analyser(page: Page, role: string, route: string, contexte: string) {
  const resultat = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  for (const v of resultat.violations) {
    for (const n of v.nodes) {
      constats.push({
        role,
        route,
        contexte,
        regle: v.id,
        gravite: v.impact,
        element: n.target.join(" "),
        aide: v.help,
      });
    }
  }
}

async function attendreEcran(page: Page) {
  await page.waitForLoadState("networkidle");
  await expect(page.locator("main#contenu")).toBeVisible();
}

/** Parcourt les routes données avec le compte donné : page chargée, puis dialogues ouverts. */
async function parcourir(
  page: Page,
  etiquette: string,
  compte: string,
  routes: readonly EntreeRoute[],
  dialoguesDe: RoleDemo | null,
) {
  await logIn(page, compte);
  const rai = await ApiSession.login(COMPTES.RAI); // lecture seule : résout les identifiants
  try {
    for (const route of routes) {
      const chemin = await resoudre(route, rai);
      if (!chemin) {
        nonResolues.push(`${etiquette} ${route.motif}`);
        continue;
      }
      await page.goto(chemin);
      await attendreEcran(page);
      await analyser(page, etiquette, route.motif, "page chargée");

      // Dialogues : déclencheurs listés puis tout déclencheur Radix de l'écran.
      const declencheurs = [
        ...DIALOGUES.filter(
          (d) => dialoguesDe !== null && d.motif === route.motif && d.roles.includes(dialoguesDe),
        ).map((d) => page.getByRole("button", { name: d.declencheur }).first()),
        ...(await page.locator('main [aria-haspopup="dialog"]').all()),
      ];
      for (const [i, declencheur] of declencheurs.entries()) {
        if (!(await declencheur.isVisible().catch(() => false))) continue;
        await declencheur.click();
        const dialogue = page.getByRole("dialog");
        if (await dialogue.isVisible().catch(() => false)) {
          await analyser(page, etiquette, route.motif, `dialogue ${i + 1}`);
          await page.keyboard.press("Escape");
          await expect(dialogue).toBeHidden();
        }
      }
    }
  } finally {
    await rai.dispose();
  }
}

for (const role of Object.keys(COMPTES) as RoleDemo[]) {
  test(`axe : routes et dialogues du rôle ${role}`, async ({ page }) => {
    test.setTimeout(30 * 60_000);
    await parcourir(
      page,
      role,
      COMPTES[role],
      ROUTES.filter((r) => r.roles.includes(role)),
      role,
    );
  });
}

// Agent non administrateur titulaire de droits délégués : l'administration des comptes.
test("axe : routes de l'administration des comptes pour un délégué", async ({ page }) => {
  test.setTimeout(10 * 60_000);
  await parcourir(
    page,
    "DELEGUE",
    COMPTE_DELEGUE,
    ROUTES.filter((r) => r.delegue),
    null,
  );
});

// Pages d'authentification sans session : connexion, mot de passe oublié, réinitialisation, erreur.
test("axe : pages publiques", async ({ page }) => {
  for (const publique of PAGES_PUBLIQUES) {
    await page.goto(publique);
    await page.waitForLoadState("networkidle");
    await analyser(page, "ANONYME", publique, "page publique");
  }
});

test.afterAll(() => {
  mkdirSync("test-results", { recursive: true });
  writeFileSync(SORTIE, JSON.stringify({ constats, nonResolues }, null, 2));
  const bloquants = constats.filter((c) => c.gravite === "serious" || c.gravite === "critical");
  console.log(
    `a11y : ${constats.length} constats, ${bloquants.length} serious/critical -> ${SORTIE}`,
  );
  if (nonResolues.length)
    console.log(`a11y : routes non résolues (données absentes) : ${nonResolues.join(", ")}`);
  if (STRICT && bloquants.length) {
    throw new Error(`${bloquants.length} violations serious/critical (voir ${SORTIE})`);
  }
});
