import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { fr } from "@/i18n/fr";
import { cn } from "@/lib/utils";
import { type ChartTable, DataTableToggle } from "./DataTableToggle";

export interface LegendItem {
  key: string;
  label: string;
  icon?: LucideIcon;
  /** Classes du pastille de couleur (ex. `bg-chart-done`). */
  swatch?: string;
}

/** Info-bulle affichée au survol et au focus (rôle `tooltip`). */
export function ChartTip({ id, children }: { id: string; children: ReactNode }) {
  return (
    <span
      role="tooltip"
      id={id}
      className="pointer-events-none absolute -top-9 left-0 z-10 rounded-md border border-border bg-surface px-2 py-1 text-xs whitespace-nowrap text-foreground shadow-floating"
    >
      {children}
    </span>
  );
}

/** Cadre de graphique : titre h3, description, légende, tracé et alternative en tableau. */
export function ChartFrame({
  title,
  description,
  legend,
  table,
  children,
  className,
}: {
  title: string;
  description?: string;
  legend?: LegendItem[];
  table: ChartTable;
  children: ReactNode;
  className?: string;
}) {
  return (
    <figure className={cn("m-0", className)}>
      <h3 className="text-base font-semibold">{title}</h3>
      {description && <p className="text-sm text-text-muted">{description}</p>}
      {legend && legend.length > 0 && (
        <ul
          aria-label={fr.charts.legend}
          className="my-2 flex list-none flex-wrap gap-x-4 gap-y-1 p-0"
        >
          {legend.map(({ key, label, icon: Icon, swatch }) => (
            <li key={key} className="flex items-center gap-1.5 text-sm">
              {swatch && <span aria-hidden="true" className={cn("size-3 rounded-sm", swatch)} />}
              {Icon && <Icon aria-hidden="true" className="size-4" />}
              {label}
            </li>
          ))}
        </ul>
      )}
      <div className="mt-2">{children}</div>
      <DataTableToggle caption={title} table={table} />
    </figure>
  );
}
