import type {
  ConclusionTest,
  FicheAction,
  MethodeSelection,
  NatureTest,
  StatutFiche,
} from "./types";

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

export const NATURE_TEST_LABELS: Record<NatureTest, string> = {
  ENTRETIEN: "Entretien",
  QCI: "Questionnaire de contrôle interne",
  OBSERVATION: "Observation physique",
  EXAMEN_DOCUMENTAIRE: "Examen documentaire",
  PROCEDURE_ANALYTIQUE: "Procédure analytique",
  PISTE_AUDIT: "Piste d'audit",
  CIRCULARISATION: "Circularisation",
  ECHANTILLONNAGE: "Échantillonnage",
  CAATS: "Technique d'audit assistée par ordinateur",
  TEST_CHEMINEMENT: "Test de cheminement",
  AUTRE: "Autre",
};

export const METHODE_SELECTION_LABELS: Record<MethodeSelection, string> = {
  EXHAUSTIF: "Exhaustif",
  ALEATOIRE: "Aléatoire",
  STATISTIQUE: "Statistique",
  RAISONNE: "Choix raisonné",
};
