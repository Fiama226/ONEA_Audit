import { z } from "zod";
import { fr } from "@/i18n/fr";

const m = fr.missionEtapes;

const charge = z
  .string()
  .trim()
  .refine((v) => v === "" || (/^\d+([.,]\d{1,2})?$/.test(v) && Number(v.replace(",", ".")) >= 0), {
    message: m.planningInvalidCharge,
  });

export const stepPlanningSchema = z
  .object({
    date_debut_prevue: z.string(),
    date_fin_prevue: z.string(),
    charge_prevue_jours: charge,
    charge_reelle_jours: charge,
  })
  .refine(
    (v) => !v.date_debut_prevue || !v.date_fin_prevue || v.date_fin_prevue >= v.date_debut_prevue,
    {
      path: ["date_fin_prevue"],
      message: m.planningEndBeforeStart,
    },
  );

export type StepPlanningValues = z.infer<typeof stepPlanningSchema>;

/** Valeurs du formulaire -> corps de requête (champ vide = `null`, virgule décimale acceptée). */
export function toPlanningPayload(values: StepPlanningValues) {
  const days = (v: string) => (v === "" ? null : v.replace(",", "."));
  return {
    date_debut_prevue: values.date_debut_prevue || null,
    date_fin_prevue: values.date_fin_prevue || null,
    charge_prevue_jours: days(values.charge_prevue_jours),
    charge_reelle_jours: days(values.charge_reelle_jours),
  };
}
