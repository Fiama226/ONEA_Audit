import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { DIALOGUES, PAGES_PUBLIQUES, ROUTES } from "../../e2e/inventaire";

const lire = (chemin: string) => readFileSync(resolve(process.cwd(), chemin), "utf8");
const motifs = new Set(ROUTES.map((r) => r.motif));
/** Connexion, mot de passe et erreur : hors du shell, couvertes par les tests de src/auth. */
const PAGES_AUTHENTIFICATION = [
  "/connexion",
  "/mot-de-passe-oublie",
  "/mot-de-passe/reinitialiser",
  "/mot-de-passe/changer",
  "/erreur",
];

/** Chemins `path:` d'un fichier de routes de fonctionnalité, préfixés ; `enfantsDe` = route parente portant des enfants. */
function cheminsDe(fichier: string, prefixe: string, enfantsDe?: string): string[] {
  const resultat: string[] = [];
  let sousParent = false;
  for (const ligne of lire(fichier).split("\n")) {
    const m = /^(\s*)(?:\{\s*)?(?:path:\s*"([^"]+)"|index:\s*true)/.exec(ligne);
    if (!m) continue;
    const indent = (m[1] ?? "").length;
    if (m[2] === undefined) continue; // route d'index : le préfixe lui-même, déjà couvert
    if (enfantsDe && m[2] === enfantsDe && indent <= 4) {
      sousParent = true;
      continue;
    }
    if (sousParent && indent < 6) sousParent = false;
    resultat.push(`${prefixe}/${sousParent && enfantsDe ? `${enfantsDe}/` : ""}${m[2]}`);
  }
  return resultat;
}

describe("test_inventaire_complet", () => {
  it("couvre toute clé de ROUTE_ROLES", () => {
    const source = lire("src/layouts/navigation.ts");
    const corps = /ROUTE_ROLES[^=]*=\s*\{([\s\S]*?)\n\};/.exec(source)?.[1] ?? "";
    const cles = [...corps.matchAll(/^\s{2}"(\/[^"]*)":/gm)].map((m) => m[1]);
    expect(cles.length).toBeGreaterThanOrEqual(8);
    for (const cle of cles) expect(motifs, `ROUTE_ROLES ${cle}`).toContain(cle);
  });

  it("couvre tout motif de route déclaré (racine et fonctionnalités)", () => {
    const attendus = [
      ...[...lire("src/routes.tsx").matchAll(/path:\s*"(\/[^"*]*)"/g)]
        .map((m) => m[1] ?? "")
        .filter((p) => !PAGES_AUTHENTIFICATION.includes(p)),
      ...cheminsDe("src/features/missions/routes.tsx", "/missions", ":id"),
      ...cheminsDe("src/features/programmation/routes.tsx", "/programme-annuel"),
      ...cheminsDe("src/features/referentiel/routes.tsx", "/referentiel"),
      ...cheminsDe("src/features/utilisateurs/routes.tsx", "/administration"),
    ];
    // Documents : deux tableaux (registre puis gabarits/numérotation).
    const [registre, admin] = lire("src/features/documents/routes.tsx").split(
      "documentsAdminRoutes",
    );
    for (const [bloc, prefixe] of [
      [registre, "/documents"],
      [admin, "/administration/documents"],
    ] as const) {
      for (const m of (bloc ?? "").matchAll(/path:\s*"([^"]+)"/g))
        attendus.push(`${prefixe}/${m[1] ?? ""}`);
    }
    // `/missions/:id` seul est une redirection d'index (pas d'écran) ; `/missions/:id/:id` est un artefact d'analyse.
    const ignores = new Set(["/missions/:id", "/missions/:id/:id"]);
    const manquants = attendus.filter((p) => !motifs.has(p) && !ignores.has(p));
    expect(manquants).toEqual([]);
  });

  it("ne référence que des écrans inventoriés pour les dialogues", () => {
    for (const d of DIALOGUES) expect(motifs, d.libelle).toContain(d.motif);
  });

  it("couvre les pages d'authentification publiques", () => {
    const publiques = PAGES_AUTHENTIFICATION.filter((p) => p !== "/mot-de-passe/changer");
    expect([...PAGES_PUBLIQUES].sort()).toEqual([...publiques].sort());
    // Le changement de mot de passe exige une session : il est parcouru avec les routes connectées.
    expect(motifs).toContain("/mot-de-passe/changer");
    expect(motifs).toContain("/mon-compte");
  });

  it("ouvre l'administration des comptes à un agent délégué", () => {
    const delegues = ROUTES.filter((r) => r.delegue).map((r) => r.motif);
    expect(delegues).toEqual(
      expect.arrayContaining([
        "/administration",
        "/administration/utilisateurs",
        "/administration/utilisateurs/:id",
      ]),
    );
    // Les gabarits et signatures restent hors délégation (lecture ADMIN et RAI).
    for (const motif of delegues) expect(motif.startsWith("/administration/documents")).toBe(false);
  });
});
