import { z } from "zod";
import { fr } from "@/i18n/fr";
import type { ActionCorrective, ActionInput } from "../types";

const t = fr.planActions;

/** Date du jour (AAAA-MM-JJ) ; l'heure d'Ouagadougou est UTC. */
export function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

/** Une échéance déjà enregistrée (`initialDue`) reste acceptée telle quelle, même dépassée. */
export function actionSchema(initialDue?: string | null) {
  return z.object({
    libelle: z.string().trim().min(1, t.requiredMeasure),
    responsable: z.string(),
    echeance: z
      .string()
      .min(1, t.requiredDue)
      .refine((value) => value >= todayIso() || value === initialDue, t.duePast),
    indicateur: z.string(),
    moyens: z.string(),
  });
}

export type ActionFormValues = z.infer<ReturnType<typeof actionSchema>>;

export const ACTION_FIELDS = [
  "libelle",
  "responsable",
  "echeance",
  "indicateur",
  "moyens",
] as const;

export function defaultActionValues(action?: ActionCorrective): ActionFormValues {
  return {
    libelle: action?.libelle ?? "",
    responsable: action?.responsable ? String(action.responsable) : "",
    echeance: action?.echeance ?? "",
    indicateur: action?.indicateur ?? "",
    moyens: action?.moyens ?? "",
  };
}

/** Charge utile API. */
export function toActionPayload(recommandation: string, values: ActionFormValues): ActionInput {
  return {
    recommandation,
    libelle: values.libelle.trim(),
    responsable: values.responsable === "" ? null : Number(values.responsable),
    echeance: values.echeance,
    indicateur: values.indicateur.trim(),
    moyens: values.moyens.trim(),
  };
}

export const riskAcceptanceSchema = z.object({
  justification: z.string().trim().min(1, t.riskJustificationRequired),
  confirme: z.boolean().refine((value) => value, t.riskConfirmRequired),
});

export type RiskAcceptanceValues = z.infer<typeof riskAcceptanceSchema>;
export const RISK_FIELDS = ["justification", "confirme"] as const;
