import { z } from "zod";
import { fr } from "@/i18n/fr";

const s = fr.refStructure;

export const auditableObjectSchema = z.object({
  libelle: z.string().trim().min(1, s.errLibelleRequired).max(200, s.errLibelleMax),
  description: z.string(),
  ordre: z.number({ error: s.errOrdre }).int(s.errOrdre).min(0, s.errOrdre),
});

export type AuditableObjectFormValues = z.infer<typeof auditableObjectSchema>;
