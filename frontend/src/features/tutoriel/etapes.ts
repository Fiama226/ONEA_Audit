import type { Role } from "@/auth/types";
import { fr } from "@/i18n/fr";

/** À incrémenter quand la visite change assez pour être reproposée à tous. */
export const TUTORIEL_VERSION = 1;

export type CleEtape = keyof typeof fr.tutoriel.steps;

export type Etape = {
  id: CleEtape;
  /** Valeurs de `data-tour` tentées dans l'ordre ; la première visible est surlignée. */
  cibles: readonly string[];
  /** Route que l'étape présente : doit être ouverte au rôle (vérifié par test). */
  route?: string;
};

const DEF: Record<CleEtape, Etape> = {
  "tableau-de-bord": {
    id: "tableau-de-bord",
    cibles: ["nav-tableau-de-bord", "menu-bouton"],
    route: "/",
  },
  menu: { id: "menu", cibles: ["menu-lateral", "menu-bouton"] },
  programme: {
    id: "programme",
    cibles: ["nav-programme-annuel", "menu-bouton"],
    route: "/programme-annuel",
  },
  missions: { id: "missions", cibles: ["nav-missions", "menu-bouton"], route: "/missions" },
  recommandations: {
    id: "recommandations",
    cibles: ["nav-recommandations", "menu-bouton"],
    route: "/recommandations",
  },
  rapports: { id: "rapports", cibles: ["nav-rapports", "menu-bouton"], route: "/rapports" },
  documents: { id: "documents", cibles: ["nav-documents", "menu-bouton"], route: "/documents" },
  administration: {
    id: "administration",
    cibles: ["nav-administration", "menu-bouton"],
    route: "/administration",
  },
  gabarits: {
    id: "gabarits",
    cibles: ["nav-gabarits", "menu-bouton"],
    route: "/administration/documents",
  },
  recherche: { id: "recherche", cibles: ["recherche"] },
  notifications: { id: "notifications", cibles: ["notifications"] },
  "menu-utilisateur": { id: "menu-utilisateur", cibles: ["menu-utilisateur"] },
};

const COMMUN_FIN: readonly CleEtape[] = ["notifications", "menu-utilisateur"];

const PAR_ROLE: Record<Role, readonly CleEtape[]> = {
  ADMIN: ["tableau-de-bord", "menu", "administration", "gabarits", ...COMMUN_FIN],
  RAI: [
    "tableau-de-bord",
    "menu",
    "programme",
    "missions",
    "recommandations",
    "recherche",
    ...COMMUN_FIN,
  ],
  AUDITEUR: [
    "tableau-de-bord",
    "menu",
    "programme",
    "missions",
    "recommandations",
    "recherche",
    ...COMMUN_FIN,
  ],
  AUDITE: [
    "tableau-de-bord",
    "menu",
    "missions",
    "recommandations",
    "documents",
    "recherche",
    ...COMMUN_FIN,
  ],
  DG: [
    "tableau-de-bord",
    "menu",
    "programme",
    "recommandations",
    "rapports",
    "recherche",
    ...COMMUN_FIN,
  ],
};

/** Étapes de la visite pour un rôle (uniquement des éléments auxquels il a accès). */
export function etapesPour(role: Role): Etape[] {
  return PAR_ROLE[role].map((id) => DEF[id]);
}
