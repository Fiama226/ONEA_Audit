// Inventaire des écrans pour l'audit d'accessibilité (lot 9, T21).
// Source de vérité du parcours axe + clavier. `src/test/inventaire-a11y.test.ts` vérifie qu'il
// couvre toute clé de ROUTE_ROLES (src/layouts/navigation.ts) et tout motif de route déclaré.

export type RoleDemo = "ADMIN" | "RAI" | "AUDITEUR" | "AUDITE" | "DG";

/**
 * Comptes e2e, créés par `manage.py creer_comptes_e2e` (scripts/e2e.sh) : le mot de passe commun
 * est E2E_PASSWORD (voir ./session.ts), sans changement forcé à la première connexion.
 */
export const COMPTES: Readonly<Record<RoleDemo, string>> = {
  ADMIN: "admin",
  RAI: "rai",
  AUDITEUR: "auditeur1",
  AUDITE: "audite1",
  DG: "dg",
};

/**
 * Compte non administrateur (AUDITEUR) qui détient tous les droits délégués de gestion des
 * comptes : il parcourt les routes marquées `delegue`.
 */
export const COMPTE_DELEGUE = "delegue1";

export const TOUS: readonly RoleDemo[] = ["ADMIN", "RAI", "AUDITEUR", "AUDITE", "DG"];

/** Ressource dont on prend le premier identifiant pour remplir les motifs `:param`. */
export type Ressource =
  | "mission"
  | "plan"
  | "ligne"
  | "cartographie"
  | "risque"
  | "processus"
  | "utilisateur"
  | "document"
  | "gabarit"
  | "rapport"
  | "action"
  | "constat"
  | "fiche";

export type EntreeRoute = {
  /** Motif exact de React Router (chemin complet). */
  motif: string;
  /** Rôles autorisés (ROUTE_ROLES du préfixe le plus long ; absent = tout authentifié). */
  roles: readonly RoleDemo[];
  /** Paramètres à résoudre par l'API de démonstration, dans l'ordre d'apparition. */
  parametres?: readonly Ressource[];
  /**
   * Route aussi ouverte, quel que soit son rôle, à l'agent qui détient un droit délégué de gestion
   * des comptes (RequireAccountManager) : parcourue en plus avec COMPTE_DELEGUE.
   */
  delegue?: true;
  /** Paramètres à valeur fixe (ex. numéro d'étape). */
  fixes?: Readonly<Record<string, string>>;
};

const MISSIONS = ["RAI", "AUDITEUR", "AUDITE"] as const;
const PROGRAMME = ["ADMIN", "RAI", "AUDITEUR", "DG"] as const;
const RECO = ["RAI", "AUDITEUR", "AUDITE", "DG"] as const;
const ADMIN_LECTURE = ["ADMIN", "RAI"] as const;

const M = "/missions/:id";
export const ROUTES: readonly EntreeRoute[] = [
  { motif: "/", roles: TOUS },
  { motif: "/notifications", roles: TOUS },
  { motif: "/recherche", roles: TOUS },
  { motif: "/missions", roles: MISSIONS },
  { motif: "/missions/nouvelle", roles: MISSIONS },
  { motif: `${M}/modifier`, roles: MISSIONS, parametres: ["mission"] },
  {
    motif: `${M}/etapes/:numero`,
    roles: MISSIONS,
    parametres: ["mission"],
    fixes: { numero: "1" },
  },
  { motif: `${M}/equipe`, roles: MISSIONS, parametres: ["mission"] },
  { motif: `${M}/reunions`, roles: MISSIONS, parametres: ["mission"] },
  { motif: `${M}/entretiens`, roles: MISSIONS, parametres: ["mission"] },
  { motif: `${M}/suivi`, roles: MISSIONS, parametres: ["mission"] },
  { motif: `${M}/referentiel-audit`, roles: MISSIONS, parametres: ["mission"] },
  { motif: `${M}/fiches/:ficheId`, roles: MISSIONS, parametres: ["mission", "fiche"] },
  { motif: `${M}/constats`, roles: MISSIONS, parametres: ["mission"] },
  { motif: `${M}/constats/:constatId`, roles: MISSIONS, parametres: ["mission", "constat"] },
  { motif: `${M}/rapport`, roles: MISSIONS, parametres: ["mission"] },
  { motif: `${M}/reponses-rapport`, roles: MISSIONS, parametres: ["mission"] },
  { motif: `${M}/plan-actions`, roles: MISSIONS, parametres: ["mission"] },
  { motif: `${M}/suivi-recommandations`, roles: MISSIONS, parametres: ["mission"] },
  { motif: "/programme-annuel", roles: PROGRAMME },
  { motif: "/programme-annuel/:id", roles: PROGRAMME, parametres: ["plan"] },
  { motif: "/programme-annuel/:id/nouvelle-ligne", roles: PROGRAMME, parametres: ["plan"] },
  { motif: "/programme-annuel/lignes/:lineId", roles: PROGRAMME, parametres: ["ligne"] },
  { motif: "/referentiel", roles: PROGRAMME },
  { motif: "/referentiel/cartographies", roles: PROGRAMME },
  { motif: "/referentiel/cartographies/:id", roles: PROGRAMME, parametres: ["cartographie"] },
  {
    motif: "/referentiel/cartographies/:id/comparer",
    roles: PROGRAMME,
    parametres: ["cartographie"],
  },
  {
    motif: "/referentiel/cartographies/:id/risques/nouveau",
    roles: PROGRAMME,
    parametres: ["cartographie"],
  },
  { motif: "/referentiel/risques/nouveau", roles: PROGRAMME },
  { motif: "/referentiel/risques/:id", roles: PROGRAMME, parametres: ["risque"] },
  { motif: "/referentiel/processus", roles: PROGRAMME },
  { motif: "/referentiel/processus/nouveau", roles: PROGRAMME },
  { motif: "/referentiel/processus/:id", roles: PROGRAMME, parametres: ["processus"] },
  { motif: "/referentiel/directions", roles: PROGRAMME },
  { motif: "/referentiel/objets-auditables", roles: PROGRAMME },
  { motif: "/recommandations", roles: RECO },
  { motif: "/recommandations/actions/:id", roles: RECO, parametres: ["action"] },
  { motif: "/rapports", roles: RECO },
  { motif: "/rapports/:id", roles: RECO, parametres: ["rapport"] },
  { motif: "/documents", roles: MISSIONS },
  { motif: "/documents/:id", roles: MISSIONS, parametres: ["document"] },
  { motif: "/administration", roles: ["ADMIN"], delegue: true },
  { motif: "/administration/utilisateurs", roles: ["ADMIN"], delegue: true },
  {
    motif: "/administration/utilisateurs/:id",
    roles: ["ADMIN"],
    delegue: true,
    parametres: ["utilisateur"],
  },
  { motif: "/administration/documents", roles: ADMIN_LECTURE },
  { motif: "/administration/documents/numerotation", roles: ADMIN_LECTURE },
  { motif: "/administration/documents/:type", roles: ADMIN_LECTURE, parametres: ["gabarit"] },
  { motif: "/administration/signatures", roles: ADMIN_LECTURE },
  { motif: "/mon-compte", roles: TOUS },
  { motif: "/mot-de-passe/changer", roles: TOUS },
];

/** Pages publiques hors coque (sans rôle, visiteur anonyme). */
export const PAGES_PUBLIQUES = [
  "/connexion",
  "/mot-de-passe-oublie",
  "/mot-de-passe/reinitialiser",
  "/erreur",
] as const;

export type EntreeDialogue = {
  /** Motif de l'écran qui porte le déclencheur (doit figurer dans ROUTES). */
  motif: string;
  roles: readonly RoleDemo[];
  /** Nom accessible du bouton qui ouvre le dialogue. */
  declencheur: RegExp;
  libelle: string;
};

/**
 * Dialogues principaux. En complément, le parcours ouvre tout bouton `aria-haspopup="dialog"`
 * de chaque écran (déclencheurs Radix). Les libellés de déclencheur sont à confirmer lors de la
 * première exécution navigateur (un déclencheur introuvable est consigné, pas fatal).
 */
export const DIALOGUES: readonly EntreeDialogue[] = [
  {
    motif: "/programme-annuel",
    roles: ["ADMIN", "RAI"],
    declencheur: /nouveau plan|créer un plan|nouveau/i,
    libelle: "Création d'un plan annuel",
  },
  {
    motif: "/administration/documents",
    roles: ["ADMIN"],
    declencheur: /téléverser|nouveau gabarit|ajouter/i,
    libelle: "Téléversement d'un gabarit",
  },
  {
    motif: "/administration/documents/numerotation",
    roles: ["ADMIN"],
    declencheur: /modifier|format/i,
    libelle: "Format de numérotation",
  },
  {
    motif: "/missions/:id/reunions",
    roles: ["RAI", "AUDITEUR"],
    declencheur: /nouvelle réunion|planifier|ajouter/i,
    libelle: "Réunion",
  },
  {
    motif: "/missions/:id/entretiens",
    roles: ["RAI", "AUDITEUR"],
    declencheur: /nouvel entretien|planifier|ajouter/i,
    libelle: "Entretien",
  },
  {
    motif: "/missions/:id/constats/:constatId",
    roles: ["AUDITE"],
    declencheur: /répondre|réponse/i,
    libelle: "Réponse de l'audité",
  },
];
