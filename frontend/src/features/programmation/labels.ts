import type { InterventionType, PlanStatus } from "./types";

export const PLAN_STATUS_LABELS: Record<PlanStatus, string> = {
  BROUILLON: "Brouillon",
  VALIDE: "Validé",
};

export const INTERVENTION_TYPE_LABELS: Record<InterventionType, string> = {
  ASSURANCE: "Assurance",
  CONSEIL: "Conseil",
};

/** « 1er trimestre », « 2e trimestre »… */
export function quarterLabel(n: number): string {
  return `${n}${n === 1 ? "er" : "e"} trimestre`;
}

export const MONTH_LABELS = [
  "janv.",
  "févr.",
  "mars",
  "avr.",
  "mai",
  "juin",
  "juil.",
  "août",
  "sept.",
  "oct.",
  "nov.",
  "déc.",
] as const;
