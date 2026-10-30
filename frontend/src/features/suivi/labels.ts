import { fr } from "@/i18n/fr";
import type {
  PrioriteRecommandation,
  StatutDemandeReport,
  StatutRecommandationSuivi,
  StatutSuivi,
  TransitionKind,
  TypeEvenementSuivi,
} from "./types";

const s = fr.suivi;

/** Libellés français des statuts de suivi (R2). */
export const STATUT_SUIVI_LABELS: Record<StatutSuivi, string> = {
  A_LANCER: s.statutA_LANCER,
  EN_COURS: s.statutEN_COURS,
  REALISEE: s.statutREALISEE,
  VERIFIEE: s.statutVERIFIEE,
  CLOTUREE: s.statutCLOTUREE,
  ABANDON_PROPOSE: s.statutABANDON_PROPOSE,
  ABANDONNEE: s.statutABANDONNEE,
};

/** Statuts après lesquels une échéance dépassée n'est plus un retard. */
export const STATUTS_SUIVI_CLOS: readonly StatutSuivi[] = ["CLOTUREE", "ABANDONNEE"];

/** Statuts pour lesquels l'échéance compte (relançables : à lancer, en cours). */
export const STATUTS_SUIVI_RELANCABLES: readonly StatutSuivi[] = ["A_LANCER", "EN_COURS"];

export const STATUT_RECOMMANDATION_SUIVI_LABELS: Record<StatutRecommandationSuivi, string> = {
  A_LANCER: s.recoA_LANCER,
  EN_COURS: s.recoEN_COURS,
  REALISEE: s.recoREALISEE,
  ABANDONNEE: s.recoABANDONNEE,
  RISQUE_ACCEPTE: s.recoRISQUE_ACCEPTE,
  SANS_ACTION: s.recoSANS_ACTION,
};

export const PRIORITE_LABELS: Record<PrioriteRecommandation, string> = {
  HAUTE: s.prioriteHAUTE,
  MOYENNE: s.prioriteMOYENNE,
  FAIBLE: s.prioriteFAIBLE,
};

export const STATUT_REPORT_LABELS: Record<StatutDemandeReport, string> = {
  EN_ATTENTE: s.reportEN_ATTENTE,
  ACCEPTEE: s.reportACCEPTEE,
  REFUSEE: s.reportREFUSEE,
};

export const EVENEMENT_LABELS: Record<TypeEvenementSuivi, string> = {
  OUVERT: s.eventOUVERT,
  DEMARRE: s.eventDEMARRE,
  COMMENTAIRE: s.eventCOMMENTAIRE,
  DECLAREE_REALISEE: s.eventDECLAREE_REALISEE,
  VERIFIEE: s.eventVERIFIEE,
  REJETEE: s.eventREJETEE,
  CLOTUREE: s.eventCLOTUREE,
  ABANDON_PROPOSE: s.eventABANDON_PROPOSE,
  ABANDON_ACCEPTE: s.eventABANDON_ACCEPTE,
  ROUVERTE: s.eventROUVERTE,
  RESPONSABLE_CHANGE: s.eventRESPONSABLE_CHANGE,
  REPORT_DEMANDE: s.eventREPORT_DEMANDE,
  REPORT_ACCEPTE: s.eventREPORT_ACCEPTE,
  REPORT_REFUSE: s.eventREPORT_REFUSE,
  PREUVE_DEPOSEE: s.eventPREUVE_DEPOSEE,
  PREUVE_RETIREE: s.eventPREUVE_RETIREE,
};

/** Champ du corps JSON propre à chaque transition (R2). */
export const TRANSITION_FIELD: Record<
  TransitionKind,
  "commentaire" | "motif" | "justification" | "texte"
> = {
  start: "commentaire",
  "declare-done": "commentaire",
  "propose-abandon": "justification",
  verify: "commentaire",
  reject: "motif",
  close: "commentaire",
  "accept-abandon": "commentaire",
  reopen: "motif",
  comment: "texte",
};
