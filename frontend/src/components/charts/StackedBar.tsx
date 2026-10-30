import { useId, useState } from "react";
import { Link } from "react-router-dom";
import { fr } from "@/i18n/fr";
import { ChartFrame, ChartTip, type LegendItem } from "./ChartFrame";
import { fmtInt, SERIE_ORDER, SERIES_STATUT, type SerieStatut } from "./palette";

export interface StackedRow {
  key: string;
  label: string;
  segments: Record<SerieStatut, number>;
  href?: string;
}

const LEGEND: LegendItem[] = SERIE_ORDER.map((k) => ({
  key: k,
  label: SERIES_STATUT[k].label,
  icon: SERIES_STATUT[k].icon,
  swatch: `${SERIES_STATUT[k].fill} ${SERIES_STATUT[k].texture ?? ""}`,
}));

const total = (r: StackedRow) => SERIE_ORDER.reduce((s, k) => s + r.segments[k], 0);
const segText = (k: SerieStatut, n: number, tot: number) =>
  fr.charts.segmentOf
    .replace("{label}", SERIES_STATUT[k].label)
    .replace("{n}", String(n))
    .replace("{total}", String(tot));

/** Barres 100 % empilées (clôturées / ouvertes / en retard) avec légende et tableau. */
export function StackedBar({ rows, ariaLabel }: { rows: StackedRow[]; ariaLabel: string }) {
  const uid = useId();
  const [active, setActive] = useState<{ row: string; seg: SerieStatut | null } | null>(null);
  return (
    <ChartFrame
      title={ariaLabel}
      legend={LEGEND}
      table={{
        columns: [fr.charts.direction, ...SERIE_ORDER.map((k) => SERIES_STATUT[k].label)],
        rows: rows.map((r) => [r.label, ...SERIE_ORDER.map((k) => r.segments[k])]),
      }}
    >
      <ul aria-label={ariaLabel} className="m-0 flex list-none flex-col gap-2 p-0">
        {rows.map((r) => {
          const tot = total(r);
          const tipId = `${uid}-${r.key}`;
          const here = active?.row === r.key ? active : null;
          const props = {
            onMouseLeave: () => setActive((a) => (a?.row === r.key ? null : a)),
            onFocus: () => setActive({ row: r.key, seg: null }),
            onBlur: () => setActive((a) => (a?.row === r.key ? null : a)),
            "aria-describedby": here ? tipId : undefined,
            className: "flex items-center gap-3 rounded-md py-0.5",
          };
          const body = (
            <>
              <span className="w-40 shrink-0 truncate text-sm sm:w-56" title={r.label}>
                {r.label}
              </span>
              <span className="flex h-3 flex-1 gap-0.5 overflow-hidden rounded-[4px] bg-surface-subtle">
                {SERIE_ORDER.filter((k) => r.segments[k] > 0).map((k) => (
                  <span
                    key={k}
                    data-segment={k}
                    onMouseEnter={() => setActive({ row: r.key, seg: k })}
                    className={`${SERIES_STATUT[k].fill} ${SERIES_STATUT[k].texture ?? ""}`}
                    style={{ width: `${(r.segments[k] / tot) * 100}%` }}
                  />
                ))}
              </span>
              <span className="w-16 shrink-0 text-right text-sm font-medium text-foreground tabular-nums">
                {fmtInt(tot)}
              </span>
            </>
          );
          return (
            <li key={r.key} className="relative">
              {r.href ? (
                <Link
                  to={r.href}
                  {...props}
                  className={`${props.className} hover:bg-surface-subtle`}
                >
                  {body}
                </Link>
              ) : (
                // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
                <div tabIndex={0} {...props}>
                  {body}
                </div>
              )}
              {here && (
                <ChartTip id={tipId}>
                  {here.seg
                    ? segText(here.seg, r.segments[here.seg], tot)
                    : SERIE_ORDER.map((k) => segText(k, r.segments[k], tot)).join(" ; ")}
                </ChartTip>
              )}
            </li>
          );
        })}
      </ul>
    </ChartFrame>
  );
}
