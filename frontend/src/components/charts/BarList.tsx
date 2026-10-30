import { useId, useState } from "react";
import { Link } from "react-router-dom";
import { fmtInt } from "./palette";
import { ChartTip } from "./ChartFrame";

export interface BarItem {
  key: string;
  label: string;
  value: number;
  href?: string;
}

/** Barres horizontales à série unique ; la valeur est toujours écrite en texte. */
export function BarList({
  data,
  ariaLabel,
  format = fmtInt,
}: {
  data: BarItem[];
  ariaLabel: string;
  format?: (n: number) => string;
}) {
  const uid = useId();
  const [active, setActive] = useState<string | null>(null);
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <ul aria-label={ariaLabel} className="m-0 flex list-none flex-col gap-2 p-0">
      {data.map((d) => {
        const tipId = `${uid}-${d.key}`;
        const row = (
          <>
            <span className="w-40 shrink-0 truncate text-sm sm:w-56" title={d.label}>
              {d.label}
            </span>
            <span className="h-3 flex-1 border-l border-foreground">
              <span
                className="block h-3 rounded-r-[4px] bg-chart-1"
                style={{ width: `${(Math.max(0, d.value) / max) * 100}%` }}
              />
            </span>
            <span className="w-16 shrink-0 text-right text-sm font-medium text-foreground tabular-nums">
              {format(d.value)}
            </span>
          </>
        );
        const handlers = {
          onMouseEnter: () => setActive(d.key),
          onMouseLeave: () => setActive((a) => (a === d.key ? null : a)),
          onFocus: () => setActive(d.key),
          onBlur: () => setActive((a) => (a === d.key ? null : a)),
          "aria-describedby": active === d.key ? tipId : undefined,
          className: "flex items-center gap-3 rounded-md py-0.5",
        };
        return (
          <li key={d.key} className="relative">
            {d.href ? (
              <Link
                to={d.href}
                {...handlers}
                className={`${handlers.className} hover:bg-surface-subtle`}
              >
                {row}
              </Link>
            ) : (
              // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
              <div tabIndex={0} {...handlers}>
                {row}
              </div>
            )}
            {active === d.key && (
              <ChartTip id={tipId}>
                {d.label} : {format(d.value)}
              </ChartTip>
            )}
          </li>
        );
      })}
    </ul>
  );
}
