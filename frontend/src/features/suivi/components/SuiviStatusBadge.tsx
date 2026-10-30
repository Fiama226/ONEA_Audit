import { StatusPill, type PillTone } from "@/components/StatusPill";
import { STATUT_SUIVI_LABELS } from "../labels";
import type { StatutSuivi } from "../types";

const TONE: Record<StatutSuivi, PillTone> = {
  A_LANCER: "neutral",
  EN_COURS: "progress",
  REALISEE: "warning",
  VERIFIEE: "progress",
  CLOTUREE: "success",
  ABANDON_PROPOSE: "warning",
  ABANDONNEE: "neutral",
};

/** Statut de suivi d'une action : point de couleur et libellé français. */
export function SuiviStatusBadge({ statut }: { statut: StatutSuivi }) {
  return <StatusPill label={STATUT_SUIVI_LABELS[statut]} tone={TONE[statut]} />;
}
