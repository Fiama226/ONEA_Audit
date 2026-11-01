import { mkdirSync, writeFileSync } from "node:fs";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { devToken } from "./api";
import {
  COMPTES,
  DIALOGUES,
  PAGES_PUBLIQUES,
  ROUTES,
  type EntreeRoute,
  type Ressource,
  type RoleDemo,
} from "./inventaire";

// Audit axe (wcag2a, wcag2aa, wcag21aa) : pour chaque rôle et chaque route autorisée, page
// chargée puis dialogues principaux ouverts. À lancer sur la base peuplée :
//   python manage.py peupler_demo --profil formation   (puis scripts/e2e.sh e2e/a11y.spec.ts)
// A11Y_STRICT=0 (défaut) : rapport JSON seul ; A11Y_STRICT=1 : échec sur serious/critical (T24, T25).
const STRICT = process.env.A11Y_STRICT === "1";
const PASSWORD = "onea2026";
const BASE = `http://localhost:${process.env.WEB_PORT ?? "5174"}`;
const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const TAGS = ["wcag2a", "wcag2aa", "wcag21aa"];
const SORTIE = "test-results/a11y-violations.json";

type Constat = {
  role: RoleDemo;
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
  utilisateur: () => "/api/v1/users/",
  document: () => "/api/v1/documents/",
  gabarit: () => "/api/v1/document-types/",
  rapport: () => "/api/v1/reports/",
  action: () => "/api/v1/follow-up/actions/",
  constat: (c) => `/api/v1/findings/?mission=${c.mission ?? ""}`,
  fiche: (c) => `/api/v1/test-sheets/?mission=${c.mission ?? ""}`,
};

async function premier(token: string, ressource: Ressource, ctx: Record<string, string>) {
  const reponse = await fetch(`${API}${LISTES[ressource](ctx)}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!reponse.ok) return null;
  const corps = (await reponse.json()) as { results?: { id?: string | number; code?: string }[] };
  const element = corps.results?.[0];
  // Les types de document/gabarit sont adressés par code, les autres par identifiant.
  return element
    ? String(ressource === "gabarit" ? (element.code ?? element.id) : element.id)
    : null;
}

async function resoudre(route: EntreeRoute, token: string): Promise<string | null> {
  const ctx: Record<string, string> = {};
  let chemin = route.motif;
  for (const [cle, valeur] of Object.entries(route.fixes ?? {}))
    chemin = chemin.replace(`:${cle}`, valeur);
  for (const ressource of route.parametres ?? []) {
    const id = await premier(token, ressource, ctx);
    if (!id) return null;
    ctx[ressource] = id;
    chemin = chemin.replace(/:[A-Za-z]+/, id); // les paramètres se remplissent dans l'ordre
  }
  return chemin;
}

async function seConnecter(page: Page, role: RoleDemo) {
  await page.goto("/");
  await page.getByRole("button", { name: "Se connecter" }).click();
  await page.waitForURL(/\/realms\/onea\/protocol\/openid-connect\/auth/);
  await page.locator("#username").fill(COMPTES[role]);
  await page.locator("#password").fill(PASSWORD);
  await page.locator("#kc-login").click();
  await page.waitForURL(`${BASE}/`);
}

async function analyser(page: Page, role: RoleDemo, route: string, contexte: string) {
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

for (const role of Object.keys(COMPTES) as RoleDemo[]) {
  test(`axe : routes et dialogues du rôle ${role}`, async ({ page }) => {
    test.setTimeout(30 * 60_000);
    const token = await devToken(COMPTES.RAI); // identifiants de démonstration : lecture seule
    await seConnecter(page, role);

    for (const route of ROUTES.filter((r) => r.roles.includes(role))) {
      const chemin = await resoudre(route, token);
      if (!chemin) {
        nonResolues.push(`${role} ${route.motif}`);
        continue;
      }
      await page.goto(chemin);
      await attendreEcran(page);
      await analyser(page, role, route.motif, "page chargée");

      // Dialogues : déclencheurs listés puis tout déclencheur Radix de l'écran.
      const declencheurs = [
        ...DIALOGUES.filter((d) => d.motif === route.motif && d.roles.includes(role)).map((d) =>
          page.getByRole("button", { name: d.declencheur }).first(),
        ),
        ...(await page.locator('main [aria-haspopup="dialog"]').all()),
      ];
      for (const [i, declencheur] of declencheurs.entries()) {
        if (!(await declencheur.isVisible().catch(() => false))) continue;
        await declencheur.click();
        const dialogue = page.getByRole("dialog");
        if (await dialogue.isVisible().catch(() => false)) {
          await analyser(page, role, route.motif, `dialogue ${i + 1}`);
          await page.keyboard.press("Escape");
          await expect(dialogue).toBeHidden();
        }
      }
    }

    // Garde de rôle : une route interdite ne doit pas afficher de contenu protégé (couvert ailleurs).
    if (role === "ADMIN") {
      for (const publique of PAGES_PUBLIQUES) {
        await page.goto(publique);
        await analyser(page, role, publique, "page publique");
      }
    }
  });
}

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
