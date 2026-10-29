import { z } from "zod";
import { fr } from "@/i18n/fr";

const c = fr.programmationPlans;

export const planSchema = z.object({
  annee: z
    .string()
    .min(1, c.requiredYear)
    .regex(/^\d{4}$/, c.invalidYear),
  libelle: z.string().trim().min(1, c.requiredLabel),
  commentaire: z.string(),
});

export type PlanFormValues = z.infer<typeof planSchema>;

export function defaultPlanLabel(year: string | number): string {
  return `${c.defaultLabel} ${year}`;
}

export const planEditSchema = z.object({
  libelle: z.string().trim().min(1, c.requiredLabel),
  commentaire: z.string(),
});

export type PlanEditValues = z.infer<typeof planEditSchema>;
