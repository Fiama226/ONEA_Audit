import { StatusPill, type PillTone } from "@/components/StatusPill";
import { PRIORITE_LABELS } from "../labels";
import type { PrioriteRecommandation } from "../types";

const TONE: Record<PrioriteRecommandation, PillTone> = {
  HAUTE: "danger",
  MOYENNE: "warning",
  FAIBLE: "neutral",
};

/** Priorité d'une recommandation. */
export function PriorityBadge({ priorite }: { priorite: PrioriteRecommandation }) {
  return <StatusPill label={PRIORITE_LABELS[priorite]} tone={TONE[priorite]} />;
}
