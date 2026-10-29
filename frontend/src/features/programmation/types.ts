import type { components } from "@/api/schema";

type S = components["schemas"];

export type AuditPlan = S["ProgrammeAnnuel"];
export type AuditPlanInput = S["ProgrammeAnnuelRequest"];
export type AuditPlanLine = S["LigneProgramme"];
export type AuditPlanLineInput = S["LigneProgrammeRequest"];
export type AuditPlanSummary = S["SyntheseProgramme"];
export type PlanStatus = S["StatutProgrammeEnum"];
export type InterventionType = S["TypeMissionEnum"];
