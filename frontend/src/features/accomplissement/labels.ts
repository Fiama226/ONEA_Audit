import type { ConclusionTest, FicheAction, StatutFiche } from "./types";

export const STATUT_FICHE_LABELS: Record<StatutFiche, string> = {
  BROUILLON: "Brouillon",
  SOUMIS: "Soumise à validation",
  VALIDE: "Validée",
  RENVOYE: "Renvoyée",
};

export const CONCLUSION_LABELS: Record<ConclusionTest, string> = {
  SATISFAISANT: "Satisfaisant",
  POINT_FORT: "Point fort",
  ANOMALIE: "Anomalie",
};

export const FICHE_ACTION_LABELS: Record<FicheAction, string> = {
  submit: "Soumettre à validation",
  validate: "Valider la fiche",
  return: "Renvoyer à l'auteur",
  reopen: "Rouvrir la fiche",
};
