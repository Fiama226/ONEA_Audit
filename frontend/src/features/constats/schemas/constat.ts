import { z } from "zod";
import { fr } from "@/i18n/fr";
import type { Constat, ConstatInput } from "../types";

const t = fr.constatsUi;

const scale = z.union([z.literal(""), z.string().regex(/^[1-5]$/, t.scaleInvalid)]);

export const constatSchema = z.object({
  titre: z.string().trim().min(1, t.requiredTitle),
  fiches: z.array(z.string()),
  entite: z.string().min(1, t.requiredEntity),
  processus: z.string().min(1, t.requiredProcess),
  risque_mission: z.string(),
  fait_constate: z.string(),
  referentiel: z.string(),
  consequence: z.string(),
  conclusion: z.string(),
  probabilite: scale,
  impact: scale,
  causes: z.array(
    z.object({
      id: z.string().optional(),
      categorie: z.enum([
        "MAIN_OEUVRE",
        "METHODES",
        "MATERIEL",
        "MILIEU",
        "MATIERE",
        "MANAGEMENT",
        "MOYENS_FINANCIERS",
      ]),
      description: z.string(),
    }),
  ),
  recommandations: z.array(
    z.object({
      id: z.string().optional(),
      libelle: z.string(),
      priorite: z.enum(["HAUTE", "MOYENNE", "FAIBLE"]),
    }),
  ),
});

export type ConstatFormValues = z.infer<typeof constatSchema>;

export const CONSTAT_FIELDS = [
  "titre",
  "fiches",
  "entite",
  "processus",
  "risque_mission",
  "fait_constate",
  "referentiel",
  "consequence",
  "conclusion",
  "probabilite",
  "impact",
] as const;

export function defaultConstatValues(
  constat: Constat | undefined,
  prefill: Partial<ConstatFormValues> = {},
): ConstatFormValues {
  return {
    titre: constat?.titre ?? "",
    fiches: constat?.fiches ?? [],
    entite: constat?.entite ?? "",
    processus: constat?.processus ?? "",
    risque_mission: constat?.risque_mission ?? "",
    fait_constate: constat?.fait_constate ?? "",
    referentiel: constat?.referentiel ?? "",
    consequence: constat?.consequence ?? "",
    conclusion: constat?.conclusion ?? "",
    probabilite: constat?.probabilite ? String(constat.probabilite) : "",
    impact: constat?.impact ? String(constat.impact) : "",
    causes: (constat?.causes ?? []).map((c) => ({
      id: c.id,
      categorie: c.categorie,
      description: c.description,
    })),
    recommandations: (constat?.recommandations ?? []).map((r) => ({
      id: r.id,
      libelle: r.libelle,
      priorite: r.priorite,
    })),
    ...prefill,
  };
}

/** Charge utile API : lignes vides retirées, ordre = position dans la liste (remplacement complet). */
export function toConstatPayload(missionId: string, values: ConstatFormValues): ConstatInput {
  return {
    mission: missionId,
    titre: values.titre.trim(),
    fiches: values.fiches,
    entite: values.entite,
    processus: values.processus,
    risque_mission: values.risque_mission === "" ? null : values.risque_mission,
    fait_constate: values.fait_constate,
    referentiel: values.referentiel,
    consequence: values.consequence,
    conclusion: values.conclusion,
    probabilite: values.probabilite === "" ? null : Number(values.probabilite),
    impact: values.impact === "" ? null : Number(values.impact),
    causes: values.causes
      .filter((c) => c.description.trim() !== "")
      .map((c, ordre) => ({ ...c, description: c.description.trim(), ordre })),
    recommandations: values.recommandations
      .filter((r) => r.libelle.trim() !== "")
      .map((r, ordre) => ({ ...r, libelle: r.libelle.trim(), ordre })),
  };
}

export const reponseSchema = z
  .object({
    position: z.enum(["", "ACCORD", "DESACCORD"]),
    commentaire: z.string(),
    confirme: z.boolean(),
  })
  .superRefine((v, ctx) => {
    if (v.position === "") {
      ctx.addIssue({ code: "custom", path: ["position"], message: t.responsePositionRequired });
    }
    if (v.position === "DESACCORD" && v.commentaire.trim() === "") {
      ctx.addIssue({ code: "custom", path: ["commentaire"], message: t.responseCommentRequired });
    }
    if (!v.confirme) {
      ctx.addIssue({ code: "custom", path: ["confirme"], message: t.responseConfirmRequired });
    }
  });

export type ReponseFormValues = z.infer<typeof reponseSchema>;

export const motifSchema = z.object({
  motif: z.string().trim().min(1, t.returnMotifRequired),
});
