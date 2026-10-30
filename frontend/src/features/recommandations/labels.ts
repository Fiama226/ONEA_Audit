import type { EtatEngagement, StatutAction, StatutRecommandationDerive } from "./types";

export const STATUT_ACTION_LABELS: Record<StatutAction, string> = {
  A_LANCER: "À lancer",
  EN_COURS: "En cours",
  REALISEE: "Réalisée",
  ABANDONNEE: "Abandonnée",
};

/** Statuts après lesquels une échéance dépassée n'est plus un retard. */
export const STATUTS_ACTION_CLOS: readonly StatutAction[] = ["REALISEE", "ABANDONNEE"];

export const STATUT_RECOMMANDATION_LABELS: Record<StatutRecommandationDerive, string> = {
  RISQUE_ACCEPTE: "Risque accepté",
  SANS_ACTION: "Sans action",
  A_LANCER: "À lancer",
  EN_COURS: "En cours",
  REALISEE: "Réalisée",
};

export const ETAT_ENGAGEMENT_LABELS: Record<EtatEngagement, string> = {
  CONFIRME: "Engagement confirmé",
  A_RENOUVELER: "Engagement à renouveler",
  NON_CONFIRME: "Engagement non confirmé",
};
