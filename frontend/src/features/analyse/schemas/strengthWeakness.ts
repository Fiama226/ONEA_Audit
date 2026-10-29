import { z } from "zod";
import { fr } from "@/i18n/fr";

const t = fr.analyseVVI;

export const strengthWeaknessSchema = z
  .object({
    type: z.enum(["", "FORCE", "FAIBLESSE"]),
    libelle: z.string().trim().min(1, t.wordingRequired).max(500, t.wordingMax),
    consequence: z.string(),
    commentaire: z.string(),
  })
  .superRefine((v, ctx) => {
    if (v.type === "") ctx.addIssue({ code: "custom", path: ["type"], message: t.typeRequired });
  });

export type StrengthWeaknessFormValues = z.infer<typeof strengthWeaknessSchema>;
