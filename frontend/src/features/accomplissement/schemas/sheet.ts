import { z } from "zod";
import { fr } from "@/i18n/fr";

const t = fr.fiches;

/** Valeurs du formulaire de fiche ; les nombres restent des chaînes jusqu'à l'envoi. */
export const sheetSchema = z.object({
  date_realisation: z.string(),
  travaux_realises: z.string(),
  echantillon_teste: z.string(),
  taille_testee: z.string().regex(/^\d*$/, t.sizeInvalid),
  nombre_exceptions: z.string().regex(/^\d*$/, t.sizeInvalid),
  resultat: z.string(),
  conclusion: z.enum(["", "SATISFAISANT", "POINT_FORT", "ANOMALIE"]),
  commentaire_conclusion: z.string(),
  charge_reelle_jours: z.string().regex(/^(\d+([.,]\d{1,2})?)?$/, t.chargeInvalid),
  justification_sans_piece: z.string(),
});

export type SheetFormValues = z.infer<typeof sheetSchema>;

export const SHEET_FIELDS = Object.keys(sheetSchema.shape) as (keyof SheetFormValues)[];

/** Corps PATCH : chaînes vides converties en null pour les champs numériques ou datés. */
export function toSheetPayload(values: SheetFormValues) {
  return {
    ...values,
    date_realisation: values.date_realisation === "" ? null : values.date_realisation,
    taille_testee: values.taille_testee === "" ? null : Number(values.taille_testee),
    nombre_exceptions: values.nombre_exceptions === "" ? null : Number(values.nombre_exceptions),
    charge_reelle_jours:
      values.charge_reelle_jours === "" ? null : values.charge_reelle_jours.replace(",", "."),
  };
}

export const testComplementarySchema = z.object({
  programme: z.string().min(1, t.compProgramRequired),
  libelle: z.string().trim().min(1, t.compLabelRequired),
  nature: z.string(),
  objectif_test: z.string(),
});

export type ComplementaryTestValues = z.infer<typeof testComplementarySchema>;
