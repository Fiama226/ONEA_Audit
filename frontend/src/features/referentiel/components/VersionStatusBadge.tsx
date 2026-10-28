import { cn } from "@/lib/utils";
import { STATUT_LABELS } from "../labels";
import type { StatutCartographie } from "../types";

const STYLE: Record<StatutCartographie, { text: string; dot: string }> = {
  BROUILLON: { text: "text-warning-text", dot: "bg-warning" },
  VALIDEE: { text: "text-success-text", dot: "bg-success" },
};

/** Statut d'une version de cartographie : point de couleur et libellé. */
export function VersionStatusBadge({
  statut,
  className,
}: {
  statut: StatutCartographie;
  className?: string;
}) {
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
      {STATUT_LABELS[statut]}
    </span>
  );
}
