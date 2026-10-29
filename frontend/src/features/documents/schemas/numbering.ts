import { z } from "zod";
import { fr } from "@/i18n/fr";

const t = fr.documentsAdmin;

export const MODEL_MAX_LENGTH = 80;
export const ABBREVIATION_MAX_LENGTH = 8;

export const numberingSchema = z.object({
  modele: z.string().trim().min(1, t.modelRequired).max(MODEL_MAX_LENGTH, t.modelMax),
  portee: z.enum(["MISSION", "ANNEE"], { message: t.scopeInvalid }),
  abreviation: z
    .string()
    .trim()
    .min(1, t.abbreviationRequired)
    .max(ABBREVIATION_MAX_LENGTH, t.abbreviationMax),
});

export type NumberingFormValues = z.infer<typeof numberingSchema>;
