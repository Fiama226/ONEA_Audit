import { z } from "zod";
import type { Rapport, RapportModification } from "../types";

/** Sections textuelles du rapport, dans l'ordre de rédaction. */
export const SECTION_FIELDS = [
  "synthese",
  "contexte",
  "objectifs_texte",
  "perimetre_texte",
  "methodologie",
  "conclusion",
  "commentaire_appreciation",
  "note_synthetique",
  "annexes_texte",
] as const;

export const reportSchema = z.object({
  synthese: z.string(),
  contexte: z.string(),
  objectifs_texte: z.string(),
  perimetre_texte: z.string(),
  methodologie: z.string(),
  conclusion: z.string(),
  commentaire_appreciation: z.string(),
  note_synthetique: z.string(),
  annexes_texte: z.string(),
  appreciation_globale: z.enum(["", "MAITRISE", "PERFECTIBLE", "INSUFFISANTE"]),
});

export type ReportFormValues = z.infer<typeof reportSchema>;

export const REPORT_FIELDS = Object.keys(reportSchema.shape) as (keyof ReportFormValues)[];

export function reportDefaults(rapport: Rapport): ReportFormValues {
  return {
    synthese: rapport.synthese,
    contexte: rapport.contexte,
    objectifs_texte: rapport.objectifs_texte,
    perimetre_texte: rapport.perimetre_texte,
    methodologie: rapport.methodologie,
    conclusion: rapport.conclusion,
    commentaire_appreciation: rapport.commentaire_appreciation,
    note_synthetique: rapport.note_synthetique,
    annexes_texte: rapport.annexes_texte,
    appreciation_globale: rapport.appreciation_globale,
  };
}

export function toReportPayload(values: ReportFormValues): RapportModification {
  return { ...values };
}
