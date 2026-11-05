import { z } from "zod";
import { fr } from "@/i18n/fr";
import type { MissionInput } from "../types";

const m = fr.missionPilotage;

const TRIGGERS = [
  "",
  "PROGRAMME_ANNUEL",
  "DEMANDE_MANAGEMENT",
  "CHANGEMENT_MAJEUR",
  "EXIGENCE_REGLEMENTAIRE",
  "AUTRE",
] as const;

/** Date calendaire `AAAA-MM-JJ`, ou chaîne vide quand elle n'est pas renseignée. */
const optionalDate = z.string();

export const missionSchema = z
  .object({
    titre: z.string().trim().min(1, m.errTitleRequired).max(300, m.errTitleMax),
    type: z.enum(["ASSURANCE", "CONSEIL"], { error: m.errTypeRequired }),
    processus: z.array(z.string()),
    entites: z.array(z.string()),
    risques_couverts: z.array(z.string()),
    evenement_declencheur: z.enum(TRIGGERS),
    evenement_precision: z.string(),
    periode_debut: optionalDate,
    periode_fin: optionalDate,
    date_debut_prevue: optionalDate,
    date_fin_prevue: optionalDate,
    budget_jours: z.string().refine((v) => v.trim() === "" || Number(v) >= 0, m.errBudget),
    objectifs: z.string(),
    perimetre: z.string(),
    exclusions: z.string(),
    clients: z.string(),
    livrables_attendus: z.string(),
  })
  .superRefine((values, ctx) => {
    const pairs = [
      ["date_debut_prevue", "date_fin_prevue"],
      ["periode_debut", "periode_fin"],
    ] as const;
    for (const [start, end] of pairs) {
      if (values[start] && values[end] && values[end] < values[start]) {
        ctx.addIssue({ code: "custom", path: [end], message: m.errDateOrder });
      }
    }
  });

export type MissionFormValues = z.infer<typeof missionSchema>;

/** Champs figés par l'ordre de mission (D17) : désactivés une fois l'étape I close. */
export const FROZEN_FIELDS = [
  "titre",
  "type",
  "processus",
  "entites",
  "risques_couverts",
  "evenement_declencheur",
  "evenement_precision",
  "periode_debut",
  "periode_fin",
  "objectifs",
  "perimetre",
  "exclusions",
  "clients",
  "livrables_attendus",
] as const satisfies readonly (keyof MissionFormValues)[];

export const FORM_FIELDS = Object.keys(missionSchema.shape) as (keyof MissionFormValues)[];

const orNull = (value: string): string | null => (value === "" ? null : value);

/** Corps complet d'une création. */
export function toPayload(values: MissionFormValues): MissionInput {
  return {
    titre: values.titre.trim(),
    type: values.type,
    processus: values.processus,
    entites: values.entites,
    risques_couverts: values.risques_couverts,
    evenement_declencheur: values.evenement_declencheur,
    evenement_precision: values.evenement_precision,
    periode_debut: orNull(values.periode_debut),
    periode_fin: orNull(values.periode_fin),
    date_debut_prevue: orNull(values.date_debut_prevue),
    date_fin_prevue: orNull(values.date_fin_prevue),
    budget_jours: orNull(values.budget_jours.trim()),
    objectifs: values.objectifs,
    perimetre: values.perimetre,
    exclusions: values.exclusions,
    clients: values.clients,
    livrables_attendus: values.livrables_attendus,
  };
}

/** Corps d'une modification ; `frozen` retire les champs D17 (le serveur les refuserait en 422). */
export function toPatch(values: MissionFormValues, frozen: boolean): Partial<MissionInput> {
  const patch: Partial<MissionInput> = toPayload(values);
  if (frozen) for (const key of FROZEN_FIELDS) delete patch[key];
  return patch;
}
