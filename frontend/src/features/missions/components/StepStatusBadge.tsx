import { cn } from "@/lib/utils";
import { STATUT_ETAPE_LABELS } from "../labels";
import type { StatutEtape } from "../types";

type Tone = { text: string; dot: string };

const STYLE: Record<StatutEtape, Tone> = {
  A_FAIRE: { text: "text-text-muted", dot: "bg-text-muted" },
  EN_COURS: { text: "text-primary", dot: "bg-primary" },
  TERMINEE: { text: "text-primary", dot: "bg-primary" },
  VALIDEE: { text: "text-success-text", dot: "bg-success" },
  RENVOYEE: { text: "text-destructive", dot: "bg-destructive" },
  A_REVALIDER: { text: "text-warning-text", dot: "bg-warning" },
  NON_APPLICABLE: { text: "text-text-muted", dot: "bg-text-muted" },
};

/** Statut d'une étape : point de couleur et libellé (jamais la couleur seule). */
export function StepStatusBadge({
  statut,
  className,
}: {
  statut: StatutEtape;
  className?: string;
}) {
  const style = STYLE[statut];
  return (
    <span
      className={cn("inline-flex items-center gap-1.5 text-xs font-medium", style.text, className)}
    >
      <span className={cn("size-2 shrink-0 rounded-full", style.dot)} aria-hidden />
      {STATUT_ETAPE_LABELS[statut]}
    </span>
  );
}
