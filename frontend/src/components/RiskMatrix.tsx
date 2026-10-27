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

const LEVEL_NAME: Record<RiskLevel, string> = {
  low: fr.dashboard.riskLow,
  medium: fr.dashboard.riskMedium,
  high: fr.dashboard.riskHigh,
};

const LEGEND: [RiskLevel, string][] = [
  ["low", fr.dashboard.levelLow],
  ["medium", fr.dashboard.levelMedium],
  ["high", fr.dashboard.levelHigh],
];

/**
 * Matrice de criticité 5 × 5. Sans `cells`, affiche l'échelle (score = probabilité × impact) ;
 * avec `cells`, une case renseignée affiche son nombre de risques à la place du score.
 * Tableau sémantique : lignes = probabilité, colonnes = impact.
 */
export function RiskMatrix({
  cells = [],
  className,
}: {
  cells?: RiskMatrixCell[];
  className?: string;
}) {
  const counts = new Map(cells.map((c) => [`${c.probability}-${c.impact}`, c.count]));
  const impact = fr.dashboard.impact.toLowerCase();
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <span aria-hidden className="rotate-180 text-xs text-text-muted [writing-mode:vertical-rl]">
        {fr.dashboard.probability}
      </span>
      <div className="min-w-0 flex-1">
        <table
          aria-label={fr.dashboard.matrixLabel}
          className="print-exact w-full max-w-[272px] border-separate [border-spacing:3px]"
        >
          <tbody>
            {[...SCALE].reverse().map((p) => (
              <tr key={p}>
                <th
                  scope="row"
                  className="w-4 pr-1 text-right text-xs font-normal text-text-muted tabular-nums"
                >
                  <span className="sr-only">{fr.dashboard.probability} </span>
                  {p}
                </th>
                {SCALE.map((i) => {
                  const score = p * i;
                  const level = riskLevel(score);
                  const count = counts.get(`${p}-${i}`);
                  const shown = count ?? score;
                  const unit = count === undefined ? "" : ` ${fr.dashboard.riskCount}`;
                  return (
                    <td
                      key={i}
                      data-level={level}
                      aria-label={`${fr.dashboard.probability} ${p}, ${impact} ${i} : ${shown}${unit}, ${LEVEL_NAME[level]}`}
                      className={cn(
                        "aspect-square rounded-[3px] text-center text-xs font-medium text-risk-foreground tabular-nums",
                        TINT[level],
                      )}
                    >
                      {shown}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td aria-hidden="true" />
              {SCALE.map((i) => (
                <th
                  key={i}
                  scope="col"
                  className="pt-1 text-center text-xs font-normal text-text-muted tabular-nums"
                >
                  <span className="sr-only">{fr.dashboard.impact} </span>
                  {i}
                </th>
              ))}
            </tr>
          </tfoot>
        </table>
        <p aria-hidden className="mt-1 text-center text-xs text-text-muted">
          {fr.dashboard.impact}
        </p>
        <ul className="mt-4 flex flex-wrap justify-center gap-x-4 gap-y-1 text-xs text-text-muted">
          {LEGEND.map(([level, label]) => (
            <li key={level} className="flex items-center gap-1.5">
              <span className={cn("size-2.5 rounded-[2px]", TINT[level])} aria-hidden />
              {label}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
