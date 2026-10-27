import { CalendarDays } from "lucide-react";
import type { ReactNode } from "react";
import type { Role } from "@/auth/types";
import { fr } from "@/i18n/fr";
import { cn } from "@/lib/utils";
import { programmeLabel } from "../year";

const dateFormat = new Intl.DateTimeFormat("fr-FR", {
  weekday: "long",
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "Africa/Ouagadougou",
});

function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function PageHeader({ title, userRole }: { title: string; userRole: Role }) {
  const now = new Date();
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
      <div>
        <h1 className="text-2xl font-semibold tracking-[-0.012em]">{title}</h1>
        <p className="mt-1 text-sm text-text-muted">
          {fr.roles[userRole]} · {programmeLabel(now)}
        </p>
      </div>
      <p className="flex items-center gap-2 text-xs text-text-muted">
        <CalendarDays className="size-4" aria-hidden />
        {capitalize(dateFormat.format(now))}
      </p>
    </div>
  );
}

/** Section « Ce que vous suivrez ici » : grille 12 colonnes (cartes empilées sous 1024 px). */
export function PreviewSection({ children }: { children: ReactNode }) {
  return (
    <>
      <div className="mt-12 mb-4 flex print:hidden flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <h2 className="text-base font-semibold">{fr.dashboard.preview}</h2>
        <p className="text-xs text-text-muted">{fr.dashboard.previewNote}</p>
      </div>
      <div className="grid grid-cols-12 items-start gap-6">{children}</div>
    </>
  );
}

const SPANS = {
  12: "col-span-12",
  8: "col-span-12 lg:col-span-8",
  7: "col-span-12 lg:col-span-7",
  5: "col-span-12 lg:col-span-5",
  4: "col-span-12 lg:col-span-4",
} as const;

type Span = keyof typeof SPANS;

/** Carte d'aperçu ; `decorative` la masque aux technologies d'assistance (aucune donnée réelle). */
export function PreviewCard({
  title,
  meta,
  span,
  decorative = true,
  children,
  bodyClassName,
}: {
  title: string;
  meta?: string;
  span: Span;
  decorative?: boolean;
  children: ReactNode;
  bodyClassName?: string;
}) {
  return (
    <section
      aria-hidden={decorative || undefined}
      className={cn(
        "rounded-lg border border-border",
        decorative ? "bg-background print:hidden" : "bg-surface",
        SPANS[span],
      )}
    >
      <div className="flex h-[52px] items-center justify-between gap-4 border-b border-border px-5">
        <h3 className="text-sm font-semibold">{title}</h3>
        {meta && <span className="text-xs text-text-muted">{meta}</span>}
      </div>
      <div className={bodyClassName}>{children}</div>
    </section>
  );
}

/** Squelette : barre grisée, sans animation. */
function Bar({ width, opacity }: { width: number | string; opacity?: number }) {
  return (
    <span
      className="inline-block h-2 rounded-[2px] bg-border/75 align-middle"
      style={{ width, opacity }}
    />
  );
}

type Column = { label: string; numeric?: boolean; width: number };

/** Tableau d'aperçu : en-têtes réels, trois lignes de squelette (opacités 100 / 70 / 40 %). */
export function SkeletonTable({ columns }: { columns: Column[] }) {
  const fades = [1, 0.7, 0.4];
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left">
        <thead>
          <tr className="h-10 border-b border-border">
            {columns.map((c) => (
              <th
                key={c.label}
                scope="col"
                className={cn(
                  "px-5 text-xs font-semibold whitespace-nowrap text-text-muted",
                  c.numeric && "text-right",
                )}
              >
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {fades.map((fade, row) => (
            <tr key={row} className="h-11 border-b border-border last:border-b-0">
              {columns.map((c) => (
                <td key={c.label} className={cn("px-5", c.numeric && "text-right")}>
                  <Bar width={c.width * (1 - row * 0.1)} opacity={fade} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

type Indicator = { label: string; foot: string };

/** Bandeau d'indicateurs : une seule carte, trois cellules séparées par des filets. */
export function StatStrip({ items }: { items: Indicator[] }) {
  return (
    <div
      aria-hidden="true"
      className="grid grid-cols-1 divide-y divide-border rounded-lg border border-border bg-background print:hidden sm:grid-cols-3 sm:divide-x sm:divide-y-0"
    >
      {items.map((item) => (
        <div key={item.label} className="px-5 py-4">
          <p className="text-xs font-medium text-text-muted">{item.label}</p>
          <p className="mt-1 text-2xl font-semibold text-text-muted tabular-nums">
            {fr.dashboard.placeholderValue}
          </p>
          <p className="mt-1 text-xs text-text-muted">{item.foot}</p>
        </div>
      ))}
    </div>
  );
}
