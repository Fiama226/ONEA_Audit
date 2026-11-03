import { useId, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import { cn } from "@/lib/utils";
import { ScrollRegion } from "@/components/ui/scroll-region";

const t = fr.tableauxDirection;

/** Section d'un tableau de bord : titre h2 relié à la région. */
export function DashSection({
  title,
  children,
  className,
}: {
  title: string;
  children: ReactNode;
  className?: string;
}) {
  const id = useId();
  return (
    <section
      aria-labelledby={id}
      className={cn("rounded-lg border border-border bg-surface p-5", className)}
    >
      <h2 id={id} className="mb-3 text-base font-semibold">
        {title}
      </h2>
      {children}
    </section>
  );
}

/** Tableau de données simple : légende, en-têtes de colonnes, ligne de message si vide. */
export function DashTable({
  caption,
  columns,
  empty,
  children,
  isEmpty,
}: {
  caption: string;
  columns: { label: string; numeric?: boolean }[];
  empty: string;
  isEmpty: boolean;
  children: ReactNode;
}) {
  if (isEmpty) return <p className="text-sm text-text-muted">{empty}</p>;
  return (
    <ScrollRegion label={caption}>
      <table className="w-full border-collapse text-left text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-border">
            {columns.map((c) => (
              <th
                key={c.label}
                scope="col"
                className={cn(
                  "px-3 py-2 text-xs font-semibold text-text-muted",
                  c.numeric && "text-right",
                )}
              >
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </ScrollRegion>
  );
}

export const CELL = "px-3 py-2 align-top";
export const ROW = "border-b border-border last:border-b-0";

/** Erreur de chargement : jamais rendue comme un tableau vide. */
export function DashError({ onRetry }: { onRetry: () => void }) {
  return (
    <div role="alert" className="rounded-lg border border-destructive p-5">
      <p className="text-sm font-medium">{t.loadError}</p>
      <Button type="button" variant="outline" size="sm" className="mt-3" onClick={onRetry}>
        {t.retry}
      </Button>
    </div>
  );
}

/** Chargement : message annoncé, le squelette est décoratif. */
export function DashLoading({ children }: { children: ReactNode }) {
  return (
    <>
      <p role="status" className="sr-only">
        {t.loading}
      </p>
      {children}
    </>
  );
}

/** Taux 0–1 du serveur (ou null) vers les pourcentages de `RateMeter`. */
export function toPercent(taux: number | null): number | null {
  return taux === null ? null : taux * 100;
}
