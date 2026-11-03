import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import { ScrollRegion } from "@/components/ui/scroll-region";

const t = fr.tableauxEquipe;

export type Column = { label: string; className?: string };

/** Tableau personnel : en-têtes, lignes ou message d'état vide. */
export function PersonalList({
  title,
  columns,
  rows,
  empty,
}: {
  title: string;
  columns: Column[];
  rows: { key: string; cells: ReactNode[] }[];
  empty: string;
}) {
  return (
    <section aria-label={title} className="rounded-lg border border-border bg-background">
      <div className="flex h-[52px] items-center justify-between gap-4 border-b border-border px-5">
        <h2 className="text-sm font-semibold">{title}</h2>
        <span className="text-xs text-text-muted tabular-nums">{rows.length}</span>
      </div>
      {rows.length === 0 ? (
        <p className="px-5 py-6 text-sm text-text-muted">{empty}</p>
      ) : (
        <ScrollRegion label={title}>
          <table className="w-full border-collapse text-left text-sm">
            <caption className="sr-only">{title}</caption>
            <thead>
              <tr className="h-10 border-b border-border">
                {columns.map((c) => (
                  <th
                    key={c.label}
                    scope="col"
                    className="px-4 text-xs font-semibold text-text-muted"
                  >
                    {c.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.key} className="min-h-11 border-b border-border last:border-b-0">
                  {row.cells.map((cell, i) => (
                    <td key={columns[i]?.label ?? i} className="px-4 py-2.5 align-middle">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollRegion>
      )}
    </section>
  );
}

/** Tuiles chiffrées d'un tableau de bord personnel. */
export function Tiles({ items }: { items: { label: string; value: number }[] }) {
  return (
    <dl
      aria-label={t.tilesLabel}
      className="grid grid-cols-1 divide-y divide-border rounded-lg border border-border bg-background sm:grid-cols-2 sm:divide-x sm:divide-y-0 lg:grid-cols-4"
    >
      {items.map((item) => (
        <div key={item.label} className="px-5 py-4">
          <dt className="text-xs font-medium text-text-muted">{item.label}</dt>
          <dd className="mt-1 text-2xl font-semibold tabular-nums">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Chargement et erreur ne sont jamais rendus comme un tableau vide. */
export function QueryState({
  isPending,
  isError,
  onRetry,
}: {
  isPending: boolean;
  isError: boolean;
  onRetry: () => void;
}) {
  if (isPending) {
    return (
      <p role="status" className="py-8 text-sm text-text-muted">
        {t.loading}
      </p>
    );
  }
  if (isError) {
    return (
      <div role="alert" className="flex flex-wrap items-center gap-4 py-8 text-sm">
        <p>{t.loadError}</p>
        <Button variant="outline" onClick={onRetry}>
          {t.retry}
        </Button>
      </div>
    );
  }
  return null;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("fr-FR", { timeZone: "Africa/Ouagadougou" }).format(new Date(iso));
}
