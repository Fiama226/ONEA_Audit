import type {
  Appreciation,
  CategorieObjectif,
  Composante,
  CouvertureOrdre,
  EvaluationConception,
  MotifNonTest,
  NatureControle,
  RoleTache,
  StatutReferentiel,
  TypeAvis,
  TypeForceFaiblesse,
  TypeQuestionnaire,
  TypologieProcessus,
  VarianteOrientation,
} from "./types";

export const APPRECIATION_LABELS: Record<Appreciation, string> = {
  OUI: "Oui",
  NON: "Non",
  SANS_OBJET: "Sans objet",
};

export const TYPE_QUESTIONNAIRE_LABELS: Record<TypeQuestionnaire, string> = {
  PRISE_CONNAISSANCE: "Questionnaire de prise de connaissance",
  QCI: "Questionnaire de contrôle interne",
};

export const TYPOLOGIE_PROCESSUS_LABELS: Record<TypologieProcessus, string> = {
  PILOTAGE: "Pilotage",
  SUPPORT: "Support",
  REALISATION: "Réalisation",
  MESURE: "Mesure",
};

export const CATEGORIE_OBJECTIF_LABELS: Record<CategorieObjectif, string> = {
  OPERATIONNELS: "Opérationnels",
  FIABILITE_INFORMATION: "Fiabilité des informations",
  STRATEGIQUES: "Stratégiques",
  CONFORMITE: "Conformité",
};

export const ROLE_TACHE_LABELS: Record<RoleTache, string> = {
  EXECUTE: "Exécute",
  AUTORISE: "Autorise",
  ENREGISTRE: "Enregistre",
  CONTROLE: "Contrôle",
};

/** Codes de la grille de séparation des tâches : E, A, En, C. */
export const ROLE_TACHE_CODES: Record<RoleTache, string> = {
  EXECUTE: "E",
  AUTORISE: "A",
  ENREGISTRE: "En",
  CONTROLE: "C",
};

export const COMPOSANTE_LABELS: Record<Composante, string> = {
  ENVIRONNEMENT: "Environnement de contrôle",
  ACTIVITE: "Activité de contrôle",
};

export const NATURE_CONTROLE_LABELS: Record<NatureControle, string> = {
  PREVENTIF: "Préventif",
  DETECTIF: "Détectif",
  CORRECTIF: "Correctif",
};

export const EVALUATION_CONCEPTION_LABELS: Record<EvaluationConception, string> = {
  ADEQUATE: "Conception adéquate — risque maîtrisé",
  INSUFFISANTE: "Conception insuffisante",
  ABSENTE: "Contrôle absent",
};

export const TYPE_FORCE_FAIBLESSE_LABELS: Record<TypeForceFaiblesse, string> = {
  FORCE: "Force",
  FAIBLESSE: "Faiblesse",
};

export const TYPE_AVIS_LABELS: Record<TypeAvis, string> = {
  ACCORD: "Accord",
  REMARQUES: "Remarques",
};

export const MOTIF_NON_TEST_LABELS: Record<MotifNonTest, string> = {
  CONTROLE_NIVEAU_SUPERIEUR: "Contrôle de niveau supérieur",
  AUTRES_CONTROLES: "Autres contrôles couvrant totalement le risque",
  CONCEPTION_ADAPTEE: "Conception adaptée",
  PERIODE_INCOMPATIBLE: "Période de mise en œuvre incompatible avec le calendrier",
  CHANGEMENT_ORGANISATION: "Changements d'organisation impactant le dispositif",
};

export const COUVERTURE_ORDRE_LABELS: Record<CouvertureOrdre, string> = {
  EXACTE: "Couverture exacte",
  ELARGIE: "Objectifs d'audit plus larges (avenant à l'ordre de mission)",
  PARTIELLE: "Objectifs d'audit ne couvrant pas tout l'ordre de mission (exclusion justifiée)",
};

export const VARIANTE_ORIENTATION_LABELS: Record<VarianteOrientation, string> = {
  COMPLET: "Rapport d'orientation complet",
  SIMPLIFIE: "Rapport d'orientation simplifié",
};

export const STATUT_REFERENTIEL_LABELS: Record<StatutReferentiel, string> = {
  BROUILLON: "En préparation",
  SOUMIS: "Soumis au RAI",
  RENVOYE: "Renvoyé",
  VALIDE: "Validé",
  A_REVALIDER: "À revalider",
};
