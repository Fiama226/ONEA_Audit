import { StatusPill, type PillTone } from "@/components/StatusPill";
import { STATUT_ACTION_LABELS } from "../labels";
import type { StatutAction } from "../types";

const TONE: Record<StatutAction, PillTone> = {
  A_LANCER: "neutral",
  EN_COURS: "progress",
  REALISEE: "success",
  ABANDONNEE: "danger",
};

/** Statut d'une action corrective. */
export function ActionStatusBadge({ statut }: { statut: StatutAction }) {
  return <StatusPill label={STATUT_ACTION_LABELS[statut]} tone={TONE[statut]} />;
}
