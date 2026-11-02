import type { ReactNode } from "react";
import { LogoMark } from "@/components/Logo";
import { fr } from "@/i18n/fr";
import { formatDateTime } from "@/lib/dates";
import { cn } from "@/lib/utils";

type Props = {
  title: string;
  /** Référence de mission (ex. MIS-2026-001), facultative. */
  reference?: string;
  orientation?: "portrait" | "paysage";
  /** Instant d'impression ; par défaut maintenant (heure d'Ouagadougou). */
  printedAt?: Date;
  children: ReactNode;
};

/**
 * Gabarit d'impression A4 commun : en-tête ONEA, titre, référence et date d'impression visibles
 * à l'impression seulement. Marges, pied « page n / N », en-têtes de tableau répétés et lignes
 * insécables : styles/print.css. Les actions de l'écran portent `print:hidden`.
 */
export function PrintLayout({
  title,
  reference,
  orientation = "portrait",
  printedAt,
  children,
}: Props) {
  const date = formatDateTime((printedAt ?? new Date()).toISOString());
  return (
    <div className={cn(orientation === "paysage" && "print-paysage")}>
      <div className="hidden border-b border-foreground pb-3 print:mb-4 print:block">
        <div className="flex items-start justify-between gap-6">
          <div className="flex items-center gap-3">
            <LogoMark className="size-10" />
            <div>
              <p className="text-xs font-bold tracking-[0.08em]">ONEA</p>
              <p className="text-[11px]">{fr.print.organisation}</p>
            </div>
          </div>
          <div className="text-right text-[11px] tabular-nums">
            {reference && (
              <p className="font-semibold">
                <span className="sr-only">{fr.impression.reference} : </span>
                {reference}
              </p>
            )}
            <p>
              {fr.impression.printedOn} {date}
            </p>
          </div>
        </div>
        <p className="mt-3 text-lg font-semibold">{title}</p>
      </div>
      {children}
    </div>
  );
}
