import { cn } from "@/lib/utils";
import { levelFromNiveau, NIVEAU_LABELS } from "../labels";
import type { NiveauRisque } from "../types";

const TINT = {
  low: "bg-risk-low",
  medium: "bg-risk-medium",
  high: "bg-risk-high",
} as const;

/** Niveau de risque : pastille colorée et texte foncé (le niveau n'est jamais porté par la couleur seule). */
export function RiskLevelBadge({
  niveau,
  className,
}: {
  niveau: NiveauRisque;
  className?: string;
}) {
  const level = levelFromNiveau(niveau);
  return (
    <span
      data-level={level}
      className={cn(
        "inline-flex h-6 items-center rounded-full px-2.5 text-xs font-medium text-risk-foreground",
        TINT[level],
        className,
      )}
    >
      {NIVEAU_LABELS[niveau]}
    </span>
  );
}
