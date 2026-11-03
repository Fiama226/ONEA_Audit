import type {
  AppreciationGlobale,
  CategorieDestinataire,
  RapportAction,
  StatutRapport,
} from "./types";

export const STATUT_RAPPORT_LABELS: Record<StatutRapport, string> = {
  BROUILLON: "Brouillon",
  SOUMIS: "Soumis à validation",
  VALIDE: "Validé",
  RENVOYE: "Renvoyé",
  DIFFUSE: "Diffusé",
  REMPLACE: "Remplacé",
};

export const APPRECIATION_LABELS: Record<AppreciationGlobale, string> = {
  MAITRISE: "Maîtrisé",
  PERFECTIBLE: "Perfectible",
  INSUFFISANTE: "Insuffisant",
};

export const CATEGORIE_DESTINATAIRE_LABELS: Record<CategorieDestinataire, string> = {
  DG: "Direction générale",
  AUDITE: "Audité",
  EQUIPE: "Équipe d'audit",
  AUTRE: "Autre",
};

export const RAPPORT_ACTION_LABELS: Record<RapportAction, string> = {
  submit: "Soumettre à validation",
  validate: "Valider le rapport",
  return: "Renvoyer pour correction",
  distribute: "Diffuser le rapport",
  correct: "Établir un rapport corrigé",
  acknowledge: "Accuser réception",
  sign: "Signer électroniquement",
};
