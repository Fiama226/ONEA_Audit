import { StatusPill, type PillTone } from "@/components/StatusPill";
import { STATUT_FICHE_LABELS } from "../labels";
import type { StatutFiche } from "../types";

const TONE: Record<StatutFiche, PillTone> = {
  BROUILLON: "neutral",
  SOUMIS: "warning",
  VALIDE: "success",
  RENVOYE: "danger",
};

/** Statut d'une fiche de test. */
export function FicheStatusBadge({ statut }: { statut: StatutFiche }) {
  return <StatusPill label={STATUT_FICHE_LABELS[statut]} tone={TONE[statut]} />;
}
