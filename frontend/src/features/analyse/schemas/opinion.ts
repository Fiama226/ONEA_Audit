import { z } from "zod";
import { fr } from "@/i18n/fr";

const t = fr.analyseVVI;

export const opinionSchema = z
  .object({
    avis: z.enum(["", "ACCORD", "REMARQUES"]),
    commentaire: z.string(),
  })
  .superRefine((v, ctx) => {
    if (v.avis === "") {
      ctx.addIssue({ code: "custom", path: ["avis"], message: t.opinionTypeRequired });
    }
    if (v.avis === "REMARQUES" && v.commentaire.trim() === "") {
      ctx.addIssue({ code: "custom", path: ["commentaire"], message: t.opinionCommentRequired });
    }
  });

export type OpinionFormValues = z.infer<typeof opinionSchema>;
