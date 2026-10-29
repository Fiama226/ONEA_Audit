import { cn } from "@/lib/utils";
import { STATUT_MISSION_LABELS } from "../labels";
import type { StatutMission } from "../types";

type Tone = { text: string; dot: string };

const NEUTRAL: Tone = { text: "text-text-muted", dot: "bg-text-muted" };
const PROGRESS: Tone = { text: "text-primary", dot: "bg-primary" };
const WARNING: Tone = { text: "text-warning-text", dot: "bg-warning" };
const SUCCESS: Tone = { text: "text-success-text", dot: "bg-success" };
const DANGER: Tone = { text: "text-destructive", dot: "bg-destructive" };

const STYLE: Record<StatutMission, Tone> = {
  BROUILLON: NEUTRAL,
  PLANIFIEE: PROGRESS,
  EN_PLANIFICATION: PROGRESS,
  EN_ACCOMPLISSEMENT: PROGRESS,
  EN_COMMUNICATION: PROGRESS,
  RAPPORT_DIFFUSE: PROGRESS,
  EN_SUIVI: PROGRESS,
  CLOTUREE: SUCCESS,
  SUSPENDUE: WARNING,
  ANNULEE: DANGER,
};

/** Statut d'une mission : point de couleur et libellé (jamais la couleur seule). */
export function MissionStatusBadge({
  statut,
  className,
}: {
  statut: StatutMission;
  className?: string;
}) {
  const style = STYLE[statut];
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center gap-1.5 rounded-full border border-border bg-surface px-2.5 text-xs font-medium whitespace-nowrap",
        style.text,
        className,
      )}
    >
      <span className={cn("size-2 rounded-full", style.dot)} aria-hidden />
      {STATUT_MISSION_LABELS[statut]}
    </span>
  );
}
