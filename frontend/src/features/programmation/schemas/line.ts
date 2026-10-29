import { z } from "zod";
import { fr } from "@/i18n/fr";

const s = fr.programmationLignes;

const DAYS = /^\d+([.,]\d)?$/;

/** Schéma du formulaire de mission prévue ; `year` est l'année du programme. */
export function lineSchema(year: number) {
  return z
    .object({
      titre: z.string().trim().min(1, s.errTitreRequired).max(300, s.errTitreMax),
      type: z.enum(["ASSURANCE", "CONSEIL"], { error: s.errTypeRequired }),
      processus: z.string().min(1, s.errProcessRequired),
      objet_auditable: z.string(),
      entites: z.array(z.string()),
      debut_prevu: z.string().min(1, s.errStartRequired),
      fin_prevue: z.string().min(1, s.errEndRequired),
      charge_prevue_jours: z.string().trim().regex(DAYS, s.errDays).or(z.literal("")),
      justification: z.string().max(5000, s.errJustificationMax),
    })
    .superRefine((v, ctx) => {
      if (v.debut_prevu && v.fin_prevue && v.fin_prevue < v.debut_prevu) {
        ctx.addIssue({ code: "custom", path: ["fin_prevue"], message: s.errEndBeforeStart });
      }
      if (v.debut_prevu && Number(v.debut_prevu.slice(0, 4)) !== year) {
        ctx.addIssue({
          code: "custom",
          path: ["debut_prevu"],
          message: s.errStartYear.replace("{annee}", String(year)),
        });
      }
    });
}

export type LineFormValues = z.infer<ReturnType<typeof lineSchema>>;

/** « 20 » ou « 20,5 » -> « 20.0 » / « 20.5 » ; vide -> null. */
export function toDecimal(value: string): string | null {
  const v = value.trim().replace(",", ".");
  return v === "" ? null : Number(v).toFixed(1);
}
