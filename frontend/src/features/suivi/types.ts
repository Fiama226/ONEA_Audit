import type { components } from "@/api/schema";

type S = components["schemas"];

export type ActionSuivie = S["SuiviAction"];
export type RecommandationSuivie = S["RecommandationSuivi"];
export type EvenementAction = S["EvenementActionSuivi"];
export type PreuveMiseEnOeuvre = S["Preuve"];
export type DemandeReport = S["DemandeReport"];
export type DemandeReportListe = S["DemandeReportListe"];
export type MissionACloturer = S["MissionACloturer"];
export type MissionSuivie = S["MissionSuivi"];
export type Relance = S["Relance"];

export type StatutSuivi = S["StatutSuiviEnum"];
export type StatutRecommandationSuivi = S["StatutRecommandationSuiviEnum"];
export type TypeEvenementSuivi = S["TypeEvenementSuiviEnum"];
export type StatutDemandeReport = S["StatutDemandeReportEnum"];
export type StatutRelance = S["StatutRelanceEnum"];
export type PalierRelance = S["PalierRelanceEnum"];
export type PrioriteRecommandation = S["PrioriteRecommandationEnum"];

/** Transitions du suivi d'une action (une route POST chacune). */
export type TransitionKind =
  | "start"
  | "declare-done"
  | "propose-abandon"
  | "verify"
  | "reject"
  | "close"
  | "accept-abandon"
  | "reopen"
  | "comment";

export type DecisionReport = "accept" | "refuse";
export type FormatExport = "csv" | "xlsx";
export type ExportKind = "actions" | "recommendations";

/** Filtres du registre : `statut` répété dans l'URL, booléens sérialisés en `true`. */
export type ActionParams = {
  annee?: number;
  mission?: string;
  recommandation?: string;
  entite?: string;
  responsable?: number;
  statut?: StatutSuivi[];
  en_retard?: boolean;
  mine?: boolean;
  echeance_avant?: string;
  echeance_apres?: string;
  ordering?: string;
  page?: number;
  page_size?: number;
};

export type RecommendationParams = {
  annee?: number;
  mission?: string;
  entite?: string;
  priorite?: PrioriteRecommandation;
  statut_suivi?: StatutRecommandationSuivi[];
  en_retard?: boolean;
  ordering?: string;
  page?: number;
  page_size?: number;
};

export type ExtensionParams = {
  action?: string;
  mission?: string;
  statut?: StatutDemandeReport;
  page?: number;
  page_size?: number;
};

export type ExtensionInput = S["DemandeReportRequestRequest"];

export type ReminderParams = {
  statut?: StatutRelance;
  mission?: string;
  page?: number;
  page_size?: number;
};
