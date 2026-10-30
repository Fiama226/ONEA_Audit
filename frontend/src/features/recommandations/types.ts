import type { components } from "@/api/schema";

type S = components["schemas"];

export type ActionCorrective = S["Action"];
export type ActionInput = S["ActionRequest"];
export type ActionUpdate = S["PatchedActionRequest"];
export type StatutAction = S["StatutActionEnum"];

export type AcceptationRisque = S["AcceptationRisque"];
export type AcceptationInput = S["AcceptationRequestRequest"];

export type EngagementPlanActions = S["EngagementPlanActions"];
export type EngagementInput = S["EngagementRequestRequest"];
export type TexteEngagement = S["TexteEngagement"];
export type EtatEngagement = S["EtatEngagementEnum"];

export type SynthesePlan = S["SynthesePlan"];
export type LigneRecommandation = S["LigneRecommandation"];
export type LigneResponsable = S["LigneResponsable"];
export type StatutRecommandationDerive = S["StatutRecommandationDeriveEnum"];
