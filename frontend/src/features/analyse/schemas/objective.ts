import { z } from "zod";
import { fr } from "@/i18n/fr";

const t = fr.analyseVII;

export const nonTestSchema = z.object({
  motif_non_test: z.string().min(1, t.reasonRequired),
  justification: z.string().trim().min(1, t.justificationRequired),
});

export type NonTestFormValues = z.infer<typeof nonTestSchema>;
