import { StatusPill, type PillTone } from "@/components/StatusPill";
import { STATUT_CONSTAT_LABELS } from "../labels";
import type { StatutConstat } from "../types";

const TONE: Record<StatutConstat, PillTone> = {
  BROUILLON: "neutral",
  SOUMIS: "warning",
  VALIDE: "success",
  RENVOYE: "danger",
};

/** Statut d'un constat. */
export function ConstatStatusBadge({ statut }: { statut: StatutConstat }) {
  return <StatusPill label={STATUT_CONSTAT_LABELS[statut]} tone={TONE[statut]} />;
}
