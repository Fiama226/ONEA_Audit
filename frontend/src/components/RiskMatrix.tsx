import { fr } from "@/i18n/fr";
import { cn } from "@/lib/utils";

export type RiskLevel = "low" | "medium" | "high";
export type RiskMatrixCell = {
  probability: 1 | 2 | 3 | 4 | 5;
  impact: 1 | 2 | 3 | 4 | 5;
  /** Nombre de risques dans la case. */
  count: number;
};

const SCALE = [1, 2, 3, 4, 5] as const;

/** Faible 1 à 7, moyen 8 à 14, élevé 15 à 25 (probabilité × impact). */
export function riskLevel(score: number): RiskLevel {
  if (score >= 15) return "high";
  if (score >= 8) return "medium";
  return "low";
}

const TINT: Record<RiskLevel, string> = {
  low: "bg-risk-low",
  medium: "bg-risk-medium",
  high: "bg-risk-high",
};

/**
 * Matrice de criticité 5 × 5. Sans `cells`, affiche l'échelle (score = probabilité × impact) ;
 * avec `cells`, une case renseignée affiche son nombre de risques à la place du score.
 */
export function RiskMatrix({
  cells = [],
  className,
}: {
  cells?: RiskMatrixCell[];
  className?: string;
}) {
  const counts = new Map(cells.map((c) => [`${c.probability}-${c.impact}`, c.count]));
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <span className="text-xs text-text-muted [text-orientation:mixed] [writing-mode:vertical-rl] rotate-180">
        {fr.dashboard.probability}
      </span>
      <div className="min-w-0 flex-1">
        <div
          role="group"
          aria-label={fr.dashboard.matrixLabel}
          className="print-exact grid max-w-[272px] grid-cols-[16px_repeat(5,1fr)] items-center gap-[3px]"
        >
          {[...SCALE].reverse().map((p) => (
            <MatrixRow key={p} probability={p} counts={counts} />
          ))}
          <span />
          {SCALE.map((i) => (
            <span key={i} className="pt-1 text-center text-xs text-text-muted tabular-nums">
              {i}
            </span>
          ))}
        </div>
        <p className="mt-1 text-center text-xs text-text-muted">{fr.dashboard.impact}</p>
        <ul className="mt-4 flex flex-wrap justify-center gap-x-4 gap-y-1 text-xs text-text-muted">
          {(["low", "medium", "high"] as const).map((level) => (
            <li key={level} className="flex items-center gap-1.5">
              <span className={cn("size-2.5 rounded-[2px]", TINT[level])} aria-hidden />
              {level === "low"
                ? fr.dashboard.levelLow
                : level === "medium"
                  ? fr.dashboard.levelMedium
                  : fr.dashboard.levelHigh}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function MatrixRow({ probability, counts }: { probability: number; counts: Map<string, number> }) {
  return (
    <>
      <span className="text-right text-xs text-text-muted tabular-nums">{probability}</span>
      {SCALE.map((impact) => {
        const score = probability * impact;
        const level = riskLevel(score);
        const count = counts.get(`${probability}-${impact}`);
        return (
          <span
            key={impact}
            data-level={level}
            className={cn(
              "flex aspect-square items-center justify-center rounded-[3px] text-xs font-medium text-risk-foreground tabular-nums",
              TINT[level],
            )}
          >
            {count ?? score}
          </span>
        );
      })}
    </>
  );
}
