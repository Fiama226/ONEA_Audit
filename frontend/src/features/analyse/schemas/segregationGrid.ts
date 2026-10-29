import { z } from "zod";
import { fr } from "@/i18n/fr";

const t = fr.analyseIII;

export const MAX_TASKS = 100;
export const MAX_ACTORS = 30;
export const LABEL_MAX = 200;

const label = z.string().trim().min(1, t.gridLabelRequired).max(LABEL_MAX, t.gridLabelMax);

/** Libellés de la grille : au moins une tâche et un acteur, bornes alignées sur le serveur. */
export const segregationGridSchema = z.object({
  taches: z.array(label).min(1, t.gridNeedTask).max(MAX_TASKS, t.gridLimits),
  acteurs: z.array(label).min(1, t.gridNeedActor).max(MAX_ACTORS, t.gridLimits),
});
