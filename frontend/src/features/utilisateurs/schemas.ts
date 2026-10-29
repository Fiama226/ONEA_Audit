import { z } from "zod";
import { fr } from "@/i18n/fr";

const t = fr.utilisateurs.fiche;

export const profileSchema = z.object({
  matricule: z.string().trim().max(32, t.matriculeMax),
  fonction: z.string().trim().max(128, t.fonctionMax),
  direction_code: z.string().trim(),
});

export type ProfileFormValues = z.infer<typeof profileSchema>;

export const deactivateSchema = z.object({
  motif: z.string().trim().min(1, t.reasonRequired).max(2000, t.reasonMax),
});

export type DeactivateFormValues = z.infer<typeof deactivateSchema>;
