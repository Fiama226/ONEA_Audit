import { z } from "zod";
import { fr } from "@/i18n/fr";

const t = fr.analyseVII;

export const orientationReportSchema = z
  .object({
    variante: z.enum(["COMPLET", "SIMPLIFIE"]),
    contexte: z.string(),
    approche: z.string(),
    observations: z.string(),
    couverture_ordre: z.enum(["", "EXACTE", "ELARGIE", "PARTIELLE"]),
    justification_couverture: z.string(),
  })
  .superRefine((v, ctx) => {
    if (
      v.couverture_ordre !== "" &&
      v.couverture_ordre !== "EXACTE" &&
      v.justification_couverture.trim() === ""
    ) {
      ctx.addIssue({
        code: "custom",
        path: ["justification_couverture"],
        message: t.coverageJustificationRequired,
      });
    }
  });

export type OrientationReportFormValues = z.infer<typeof orientationReportSchema>;
