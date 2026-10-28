import type { RiskLevel } from "@/components/RiskMatrix";
import type {
  FamilleProcessus,
  NatureObjet,
  NiveauRisque,
  PrioriteRisque,
  ReponseRisque,
  StatutCartographie,
  TypeEntite,
} from "./types";

export const FAMILLE_LABELS: Record<FamilleProcessus, string> = {
  PILOTAGE: "Pilotage",
  REALISATION: "Réalisation",
  SUPPORT: "Support",
};

export const TYPE_ENTITE_LABELS: Record<TypeEntite, string> = {
  DIRECTION: "Direction",
  DEPARTEMENT: "Département",
};

export const NATURE_LABELS: Record<NatureObjet, string> = {
  DOMAINE: "Domaine",
  OPERATION: "Opération",
};

export const STATUT_LABELS: Record<StatutCartographie, string> = {
  BROUILLON: "Brouillon",
  VALIDEE: "Validée",
};

export const NIVEAU_LABELS: Record<NiveauRisque, string> = {
  FAIBLE: "Faible",
  MOYEN: "Moyen",
  ELEVE: "Élevé",
};

export const REPONSE_LABELS: Record<ReponseRisque, string> = {
  TRAITER: "Traiter",
  TRANSFERER: "Transférer",
  TERMINER: "Terminer",
  TOLERER: "Tolérer",
};

export const PRIORITE_LABELS: Record<PrioriteRisque, string> = {
  1: "Prioritaire",
  2: "Amélioration",
  3: "Observation",
};

const LEVELS: Record<NiveauRisque, RiskLevel> = { FAIBLE: "low", MOYEN: "medium", ELEVE: "high" };

/** Niveau serveur (FAIBLE / MOYEN / ELEVE) vers le niveau visuel de la matrice. */
export function levelFromNiveau(n: NiveauRisque): RiskLevel {
  return LEVELS[n];
}
