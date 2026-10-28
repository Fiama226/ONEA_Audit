import { z } from "zod";
import { fr } from "@/i18n/fr";

const c = fr.refCartographie;

export const riskMapSchema = z.object({
  annee: z
    .string()
    .min(1, c.requiredAnnee)
    .regex(/^\d{4}$/, c.invalidAnnee),
  libelle: z.string().trim().min(1, c.requiredLibelle),
  commentaire: z.string(),
  source: z.string(),
});

export type RiskMapFormValues = z.infer<typeof riskMapSchema>;

export function defaultRiskMapLibelle(annee: string | number): string {
  return `${c.defaultLibelle} ${annee}`;
}

export const riskMapEditSchema = z.object({
  libelle: z.string().trim().min(1, c.requiredLibelle),
  commentaire: z.string(),
});

export type RiskMapEditValues = z.infer<typeof riskMapEditSchema>;
