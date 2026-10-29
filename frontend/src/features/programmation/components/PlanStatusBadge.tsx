import { cn } from "@/lib/utils";
import { PLAN_STATUS_LABELS } from "../labels";
import type { PlanStatus } from "../types";

const STYLE: Record<PlanStatus, { text: string; dot: string }> = {
  BROUILLON: { text: "text-warning-text", dot: "bg-warning" },
  VALIDE: { text: "text-success-text", dot: "bg-success" },
};

/** Statut d'un programme annuel : point de couleur et libellé. */
export function PlanStatusBadge({ statut, className }: { statut: PlanStatus; className?: string }) {
  const style = STYLE[statut];
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center gap-1.5 rounded-full border border-border bg-surface px-2.5 text-xs font-medium",
        style.text,
        className,
      )}
    >
      <span className={cn("size-2 rounded-full", style.dot)} aria-hidden />
      {PLAN_STATUS_LABELS[statut]}
    </span>
  );
}
