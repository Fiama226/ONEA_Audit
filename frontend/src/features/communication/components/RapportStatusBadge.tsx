import { StatusPill, type PillTone } from "@/components/StatusPill";
import { STATUT_RAPPORT_LABELS } from "../labels";
import type { StatutRapport } from "../types";

const TONE: Record<StatutRapport, PillTone> = {
  BROUILLON: "neutral",
  SOUMIS: "warning",
  VALIDE: "progress",
  RENVOYE: "danger",
  DIFFUSE: "success",
  REMPLACE: "neutral",
};

/** Statut d'un rapport d'audit. */
export function RapportStatusBadge({ statut }: { statut: StatutRapport }) {
  return <StatusPill label={STATUT_RAPPORT_LABELS[statut]} tone={TONE[statut]} />;
}
