import { StatusPill, type PillTone } from "@/components/StatusPill";
import { POSITION_LABELS } from "../labels";
import type { PositionAudite } from "../types";

const TONE: Record<PositionAudite, PillTone> = { ACCORD: "success", DESACCORD: "danger" };

/** Position de l'audité sur un constat. */
export function PositionBadge({ position }: { position: PositionAudite }) {
  return <StatusPill label={POSITION_LABELS[position]} tone={TONE[position]} />;
}
