import { z } from "zod";
import { fr } from "@/i18n/fr";

const s = fr.refStructure;

export const processSchema = z.object({
  code: z.string().regex(/^[A-Z]{2,5}$/, s.errCodeProcess),
  libelle: z.string().trim().min(1, s.errLibelleRequired).max(200, s.errLibelleMax),
  famille: z.enum(["PILOTAGE", "REALISATION", "SUPPORT"], { error: s.errFamilyRequired }),
  ordre: z.number({ error: s.errOrdre }).int(s.errOrdre).min(0, s.errOrdre),
  directions: z.array(z.string()),
});

export type ProcessFormValues = z.infer<typeof processSchema>;
