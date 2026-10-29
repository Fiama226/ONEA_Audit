import { z } from "zod";
import { fr } from "@/i18n/fr";

const t = fr.analyseVVI;

export const marcLineSchema = z
  .object({
    risque: z.string().min(1, t.riskRequired),
    objet_auditable: z.string(),
    operation: z.string().max(300),
    objectif_controle: z.string(),
    controle_attendu: z.string(),
    controle_existant: z.string(),
    composante: z.enum(["", "ENVIRONNEMENT", "ACTIVITE"]),
    nature: z.enum(["", "PREVENTIF", "DETECTIF", "CORRECTIF"]),
    evaluation: z.enum(["", "ADEQUATE", "INSUFFISANTE", "ABSENTE"]),
    cle: z.boolean(),
    commentaire: z.string(),
  })
  .superRefine((v, ctx) => {
    if (
      (v.evaluation === "ADEQUATE" || v.evaluation === "INSUFFISANTE") &&
      v.controle_existant.trim() === ""
    ) {
      ctx.addIssue({ code: "custom", path: ["controle_existant"], message: t.existingRequired });
    }
    if (v.cle && v.evaluation === "ABSENTE") {
      ctx.addIssue({ code: "custom", path: ["cle"], message: t.keyForbidden });
    }
  });

export type MarcLineFormValues = z.infer<typeof marcLineSchema>;
