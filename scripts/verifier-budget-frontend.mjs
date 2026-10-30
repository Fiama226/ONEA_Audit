#!/usr/bin/env node
// Vérifie les budgets de taille du frontend (D10) à partir de dist/.vite/manifest.json.
// Mesure en gzip : JS initial (entrée + dépendances statiques), chaque morceau chargé à la
// demande, CSS. Budgets surchargeables : BUDGET_ENTREE_KO, BUDGET_MORCEAU_KO, BUDGET_CSS_KO.
// Répertoire dist : premier argument ou FRONTEND_DIST (défaut : frontend/dist).
// Code de sortie 1 au dépassement, 2 si le manifeste est absent ou une variable invalide.
import { readFileSync, existsSync } from "node:fs";
import { gzipSync } from "node:zlib";
import path from "node:path";
import { fileURLToPath } from "node:url";

const racine = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const dist = path.resolve(
  process.argv[2] ??
    process.env.FRONTEND_DIST ??
    path.join(racine, "frontend", "dist"),
);

function budget(nom, defaut) {
  const brut = process.env[nom];
  if (brut === undefined || brut === "") return defaut;
  const valeur = Number(brut);
  if (!Number.isFinite(valeur) || valeur <= 0) {
    console.error(`${nom} doit être un nombre positif (reçu « ${brut} »).`);
    process.exit(2);
  }
  return valeur;
}

const BUDGET_ENTREE_KO = budget("BUDGET_ENTREE_KO", 250);
const BUDGET_MORCEAU_KO = budget("BUDGET_MORCEAU_KO", 150);
const BUDGET_CSS_KO = budget("BUDGET_CSS_KO", 60);

const fichierManifeste = path.join(dist, ".vite", "manifest.json");
if (!existsSync(fichierManifeste)) {
  console.error(
    `Manifeste introuvable : ${fichierManifeste} (lancer « npm run build » d'abord).`,
  );
  process.exit(2);
}
const manifeste = JSON.parse(readFileSync(fichierManifeste, "utf8"));

const gzipKo = (fichier) =>
  gzipSync(readFileSync(path.join(dist, fichier))).length / 1024;

const entrees = Object.keys(manifeste).filter((cle) => manifeste[cle].isEntry);
if (entrees.length === 0) {
  console.error("Aucune entrée dans le manifeste.");
  process.exit(2);
}

// Fichiers JS chargés statiquement au démarrage (entrée + imports statiques, transitifs).
const initiaux = new Set();
function parcourir(cle) {
  const m = manifeste[cle];
  if (!m || initiaux.has(m.file)) return;
  initiaux.add(m.file);
  for (const dep of m.imports ?? []) parcourir(dep);
}
entrees.forEach(parcourir);

const fichiersJs = new Map();
const fichiersCss = new Set();
for (const m of Object.values(manifeste)) {
  if (m.file.endsWith(".js")) fichiersJs.set(m.file, m);
  for (const css of m.css ?? []) fichiersCss.add(css);
}

const lignes = [];
let initial = 0;
for (const f of initiaux) initial += gzipKo(f);
lignes.push({
  nom: "JS d'entrée (initial)",
  ko: initial,
  budget: BUDGET_ENTREE_KO,
});

for (const [f, m] of [...fichiersJs].sort(([a], [b]) => a.localeCompare(b))) {
  if (initiaux.has(f)) continue;
  lignes.push({
    nom: `morceau ${m.name ?? f}`,
    ko: gzipKo(f),
    budget: BUDGET_MORCEAU_KO,
  });
}

let css = 0;
for (const f of fichiersCss) css += gzipKo(f);
lignes.push({ nom: "CSS (total)", ko: css, budget: BUDGET_CSS_KO });

const largeur = Math.max(...lignes.map((l) => l.nom.length), "Élément".length);
let echec = false;
console.log(`${"Élément".padEnd(largeur)}  gzip (ko)  budget (ko)  état`);
for (const l of lignes) {
  const ok = l.ko <= l.budget;
  if (!ok) echec = true;
  console.log(
    `${l.nom.padEnd(largeur)}  ${l.ko.toFixed(1).padStart(9)}  ${String(l.budget).padStart(11)}  ${ok ? "OK" : "DÉPASSÉ"}`,
  );
}
if (echec) {
  console.error("Budget frontend dépassé.");
  process.exit(1);
}
console.log("Budgets frontend respectés.");
