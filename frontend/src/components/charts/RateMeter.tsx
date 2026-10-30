import { fr } from "@/i18n/fr";
import { fmtInt } from "./palette";

/** Taux en pourcentage (`rate` de 0 à 100, `null` si le dénominateur est nul). */
export function RateMeter({
  label,
  rate,
  numerator,
  denominator,
}: {
  label: string;
  rate: number | null;
  numerator: number;
  denominator: number;
}) {
  const pct = rate === null ? null : Math.min(100, Math.max(0, Math.round(rate)));
  const text =
    pct === null
      ? `${fr.charts.none} (${fr.charts.noAction})`
      : `${pct} % (${fmtInt(numerator)} sur ${fmtInt(denominator)})`;
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between gap-3 text-sm">
        <span>{label}</span>
        <span className="font-medium text-foreground tabular-nums">{text}</span>
      </div>
      <div
        {...(pct !== null && {
          role: "meter",
          "aria-label": label,
          "aria-valuenow": pct,
          "aria-valuemin": 0,
          "aria-valuemax": 100,
          "aria-valuetext": text,
        })}
        aria-hidden={pct === null ? true : undefined}
        className="h-2 overflow-hidden rounded-[4px] bg-surface-subtle"
      >
        <div className="h-2 bg-chart-1" style={{ width: `${pct ?? 0}%` }} />
      </div>
    </div>
  );
}
