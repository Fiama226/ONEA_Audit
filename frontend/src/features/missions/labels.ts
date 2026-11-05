import type {
  ActionEtape,
  EvenementDeclencheur,
  Phase,
  RoleMission,
  StatutDeclaration,
  StatutEntretien,
  StatutEtape,
  StatutMission,
  TypeEvenementEtape,
  TypeMission,
  TypeReunion,
} from "./types";

export const STATUT_MISSION_LABELS: Record<StatutMission, string> = {
  BROUILLON: "Brouillon",
  PLANIFIEE: "Planifiée",
  EN_PLANIFICATION: "En planification",
  EN_ACCOMPLISSEMENT: "En accomplissement",
  EN_COMMUNICATION: "En communication",
  RAPPORT_DIFFUSE: "Rapport diffusé",
  EN_SUIVI: "En suivi",
  CLOTUREE: "Clôturée",
  SUSPENDUE: "Suspendue",
  ANNULEE: "Annulée",
};

export const STATUT_ETAPE_LABELS: Record<StatutEtape, string> = {
  A_FAIRE: "À faire",
  EN_COURS: "En cours",
  TERMINEE: "Terminée",
  VALIDEE: "Validée",
  RENVOYEE: "Renvoyée",
  A_REVALIDER: "À revalider",
  NON_APPLICABLE: "Non applicable",
};

export const PHASE_LABELS: Record<Phase, string> = {
  PLANIFICATION: "Planification",
  ACCOMPLISSEMENT: "Accomplissement",
  COMMUNICATION: "Communication",
};

/** Étendue des étapes de chaque phase, en chiffres romains. */
export const PHASE_RANGES: Record<Phase, string> = {
  PLANIFICATION: "I–X",
  ACCOMPLISSEMENT: "XI–XIV",
  COMMUNICATION: "XV–XVIII",
};

export const PHASE_ORDER: readonly Phase[] = ["PLANIFICATION", "ACCOMPLISSEMENT", "COMMUNICATION"];

export const ACTION_LABELS: Record<ActionEtape, string> = {
  DEMARRER: "Commencer l'étape",
  TERMINER: "Terminer l'étape",
  VALIDER: "Valider le jalon",
  RENVOYER: "Renvoyer",
  ROUVRIR: "Rouvrir l'étape",
  NON_APPLICABLE: "Marquer non applicable",
  RETABLIR: "Rétablir l'étape",
  PLANIFIER: "Planifier l'étape",
};

export const TYPE_MISSION_LABELS: Record<TypeMission, string> = {
  ASSURANCE: "Assurance",
  CONSEIL: "Conseil",
};

export const ROLE_MISSION_LABELS: Record<RoleMission, string> = {
  CHEF_MISSION: "Chef de mission",
  AUDITEUR: "Auditeur",
  SUPERVISEUR: "Superviseur",
  AUDITE: "Audité",
};

export const STATUT_DECLARATION_LABELS: Record<StatutDeclaration, string> = {
  EN_ATTENTE: "En attente",
  CONFIRMEE: "Confirmée",
  CONFLIT_DECLARE: "Conflit déclaré",
};

export const STATUT_ENTRETIEN_LABELS: Record<StatutEntretien, string> = {
  PLANIFIE: "Planifié",
  REALISE: "Réalisé",
  ANNULE: "Annulé",
};

export const TYPE_REUNION_LABELS: Record<TypeReunion, string> = {
  OUVERTURE: "Réunion d'ouverture",
  LANCEMENT: "Réunion de lancement",
  CLOTURE: "Réunion de clôture",
};

export const EVENEMENT_DECLENCHEUR_LABELS: Record<EvenementDeclencheur, string> = {
  PROGRAMME_ANNUEL: "Mission inscrite au programme annuel",
  DEMANDE_MANAGEMENT: "Demande du management",
  CHANGEMENT_MAJEUR: "Changement majeur interne ou externe",
  EXIGENCE_REGLEMENTAIRE: "Exigence réglementaire",
  AUTRE: "Autre",
};

export const TYPE_EVENEMENT_ETAPE_LABELS: Record<TypeEvenementEtape, string> = {
  DEMARREE: "Étape commencée",
  TERMINEE: "Étape terminée",
  VALIDEE: "Jalon validé",
  RENVOYEE: "Étape renvoyée",
  ROUVERTE: "Étape rouverte",
  A_REVALIDER: "À revalider",
  NON_APPLICABLE: "Marquée non applicable",
  RETABLIE: "Étape rétablie",
  DEROGATION: "Dérogation à la réponse de l'audité",
};
