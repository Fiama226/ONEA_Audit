import { z } from "zod";
import { fr } from "@/i18n/fr";

const s = fr.refStructure;

export const directionSchema = z
  .object({
    code: z.string().regex(/^[A-Z][A-Z0-9-]{1,15}$/, s.errCodeDirection),
    libelle: z.string().trim().min(1, s.errLibelleRequired).max(200, s.errLibelleMax),
    type: z.enum(["DIRECTION", "DEPARTEMENT"], { error: s.errTypeRequired }),
    parent: z.string(),
  })
  .refine((v) => v.type !== "DEPARTEMENT" || v.parent !== "", {
    path: ["parent"],
    message: s.errParentRequired,
  });

export type DirectionFormValues = z.infer<typeof directionSchema>;
