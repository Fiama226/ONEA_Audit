import { z } from "zod";
import { fr } from "@/i18n/fr";
import { METHODE_SELECTION_LABELS, NATURE_TEST_LABELS } from "../labels";
import type { MethodeSelection, NatureTest, TestPrevuInput } from "../types";

const t = fr.programme;

export const plannedTestSchema = z.object({
  libelle: z.string().trim().min(1, t.labelRequired).max(300, t.labelTooLong),
  objectif_test: z.string(),
  nature: z.string().min(1, t.natureRequired),
  procedure: z.string(),
  population: z.string(),
  taille_echantillon: z
    .string()
    .trim()
    .refine((v) => v === "" || /^[1-9]\d*$/.test(v), t.sizeInvalid),
  methode_selection: z.string(),
  risque_mission: z.string(),
});

export type PlannedTestFormValues = z.infer<typeof plannedTestSchema>;

export const EMPTY_PLANNED_TEST: PlannedTestFormValues = {
  libelle: "",
  objectif_test: "",
  nature: "",
  procedure: "",
  population: "",
  taille_echantillon: "",
  methode_selection: "",
  risque_mission: "",
};

/** Corps de la requête : les champs facultatifs vides ne sont pas envoyés. */
export function toPlannedTestInput(
  programme: string,
  values: PlannedTestFormValues,
): TestPrevuInput {
  const input: TestPrevuInput = {
    programme,
    libelle: values.libelle.trim(),
    nature: values.nature as NatureTest,
  };
  if (values.objectif_test.trim()) input.objectif_test = values.objectif_test.trim();
  if (values.procedure.trim()) input.procedure = values.procedure.trim();
  if (values.population.trim()) input.population = values.population.trim();
  if (values.taille_echantillon.trim()) {
    input.taille_echantillon = Number(values.taille_echantillon);
  }
  if (values.methode_selection) {
    input.methode_selection = values.methode_selection as MethodeSelection;
  }
  if (values.risque_mission) input.risque_mission = values.risque_mission;
  return input;
}

export const NATURES = Object.keys(NATURE_TEST_LABELS) as NatureTest[];
export const METHODES = Object.keys(METHODE_SELECTION_LABELS) as MethodeSelection[];

export const resourcesSchema = z
  .object({
    auditeur: z.string(),
    charge_prevue_jours: z
      .string()
      .trim()
      .refine(
        (v) => v === "" || (/^\d+([.,]\d{1,2})?$/.test(v) && Number(v.replace(",", ".")) >= 0),
        t.loadInvalid,
      ),
    date_debut_prevue: z.string(),
    date_fin_prevue: z.string(),
  })
  .superRefine((v, ctx) => {
    if (v.date_debut_prevue && v.date_fin_prevue && v.date_fin_prevue < v.date_debut_prevue) {
      ctx.addIssue({ code: "custom", path: ["date_fin_prevue"], message: t.datesInvalid });
    }
  });

export type ResourcesFormValues = z.infer<typeof resourcesSchema>;
