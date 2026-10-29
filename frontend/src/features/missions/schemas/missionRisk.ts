import { z } from "zod";
import { fr } from "@/i18n/fr";
import { NIVEAU_LABELS } from "@/features/referentiel/labels";
import { niveauFromScore } from "@/features/referentiel/schemas/risk";

const m = fr.missionEtapes;

const scale = z.string().regex(/^[1-5]$/, m.requiredScale);

export const newMissionRiskSchema = z.object({
  processus: z.string().min(1, m.requiredProcess),
  libelle: z.string().trim().min(1, m.requiredLabel).max(500, m.maxLabel),
  description: z.string(),
  probabilite: scale,
  impact: scale,
});

export const reevaluateMissionRiskSchema = z.object({
  probabilite: scale,
  impact: scale,
  commentaire: z.string(),
});

export type NewMissionRiskValues = z.infer<typeof newMissionRiskSchema>;
export type ReevaluateMissionRiskValues = z.infer<typeof reevaluateMissionRiskSchema>;

/** Aperçu client « Score 15 · Élevé » ; le serveur reste l'autorité pour le score. */
export function riskPreview(probabilite: string, impact: string): string | null {
  const p = Number(probabilite);
  const i = Number(impact);
  if (!(p >= 1 && p <= 5 && i >= 1 && i <= 5)) return null;
  const score = p * i;
  return m.preview
    .replace("{score}", String(score))
    .replace("{niveau}", NIVEAU_LABELS[niveauFromScore(score)]);
}
