export const fr = {
  app: {
    name: "Audit interne ONEA",
    tagline: "Plateforme de conduite des missions d'audit interne",
  },
  nav: {
    dashboard: "Tableau de bord",
    missions: "Missions",
    referentiel: "Référentiel",
    risques: "Cartographie des risques",
    recommandations: "Recommandations",
    documents: "Documents",
    administration: "Administration",
  },
  auth: {
    login: "Se connecter",
    logout: "Se déconnecter",
    username: "Identifiant",
    password: "Mot de passe",
    sessionExpired: "Votre session a expiré. Veuillez vous reconnecter.",
    loginPrompt: "Connectez-vous avec votre compte ONEA pour accéder à la plateforme.",
  },
  errors: {
    generic: "Une erreur est survenue. Veuillez réessayer.",
    network: "Le serveur est injoignable. Vérifiez votre connexion.",
    unreachableTitle: "Service indisponible",
    unreachable:
      "Le serveur ou le service d'authentification est injoignable. Veuillez réessayer dans quelques instants.",
    unauthorized: "Vous devez être connecté pour accéder à cette page.",
    forbidden: "Vous n'avez pas les droits nécessaires pour cette action.",
    notFound: "La ressource demandée est introuvable.",
    validation: "Certaines données sont invalides. Veuillez les corriger.",
  },
  common: {
    save: "Enregistrer",
    cancel: "Annuler",
    confirm: "Confirmer",
    delete: "Supprimer",
    edit: "Modifier",
    create: "Créer",
    search: "Rechercher",
    retry: "Réessayer",
    loading: "Chargement en cours",
    empty: "Aucun élément à afficher.",
    close: "Fermer",
    more: "Plus",
    breadcrumb: "Fil d'Ariane",
    actions: "Actions",
    yes: "Oui",
    no: "Non",
  },
} as const;

/** Clés "section.libellé" : le dictionnaire a exactement deux niveaux. */
export type TranslationKey = {
  [S in keyof typeof fr & string]: `${S}.${keyof (typeof fr)[S] & string}`;
}[keyof typeof fr & string];

/** Résolution stricte : une clé inconnue est une erreur de compilation. */
export function t(key: TranslationKey): string {
  let node: unknown = fr;
  for (const part of key.split(".")) {
    if (typeof node !== "object" || node === null || !(part in node)) {
      throw new Error(`Clé de traduction inconnue : ${key}`);
    }
    node = (node as Record<string, unknown>)[part];
  }
  if (typeof node !== "string") throw new Error(`Clé de traduction invalide : ${key}`);
  return node;
}
