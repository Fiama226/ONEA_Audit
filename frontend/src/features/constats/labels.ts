import type {
  CategorieCause,
  ConstatAction,
  PositionAudite,
  PrioriteRecommandation,
  StatutConstat,
} from "./types";

export const STATUT_CONSTAT_LABELS: Record<StatutConstat, string> = {
  BROUILLON: "Brouillon",
  SOUMIS: "Soumis à l'audité",
  VALIDE: "Validé",
  RENVOYE: "Renvoyé",
};

/** Les six « M » d'Ishikawa et les moyens financiers. */
export const CATEGORIE_CAUSE_LABELS: Record<CategorieCause, string> = {
  MAIN_OEUVRE: "Main-d'œuvre",
  METHODES: "Méthodes",
  MATERIEL: "Matériel",
  MILIEU: "Milieu",
  MATIERE: "Matière",
  MANAGEMENT: "Management",
  MOYENS_FINANCIERS: "Moyens financiers",
};

export const PRIORITE_LABELS: Record<PrioriteRecommandation, string> = {
  HAUTE: "Haute",
  MOYENNE: "Moyenne",
  FAIBLE: "Faible",
};

export const POSITION_LABELS: Record<PositionAudite, string> = {
  ACCORD: "D'accord",
  DESACCORD: "En désaccord",
};

export const CONSTAT_ACTION_LABELS: Record<ConstatAction, string> = {
  submit: "Soumettre à l'audité",
  validate: "Valider le constat",
  return: "Renvoyer à l'auteur",
  reopen: "Rouvrir le constat",
};
