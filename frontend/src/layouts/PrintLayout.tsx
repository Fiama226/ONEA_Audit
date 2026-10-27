import type { ReactNode } from "react";
import { LogoMark } from "@/components/Logo";
import { fr } from "@/i18n/fr";

type Props = {
  /** Référence de la mission (ex. MIS-2026-001). */
  reference: string;
  documentType?: string;
  version?: string;
  status?: string;
  /** « JJ/MM/AAAA à HH:MM » (heure d'Ouagadougou), déjà formaté. */
  printedAt?: string;
  printedBy?: string;
  children: ReactNode;
};

/**
 * Gabarit d'impression A4 (noir sur blanc). Les marges et la pagination « Page N sur M »
 * sont définies par `@page` dans globals.css ; l'en-tête et le pied sont répétés à
 * l'impression (position fixe, repli quand les marges de page ne sont pas prises en charge).
 */
export function PrintLayout({
  reference,
  documentType,
  version,
  status,
  printedAt,
  printedBy,
  children,
}: Props) {
  return (
    <div className="bg-surface text-foreground">
      <header className="flex items-start justify-between gap-6 border-b border-foreground pb-3 print:fixed print:top-0 print:right-0 print:left-0 print:bg-surface">
        <div className="flex items-center gap-3">
          <LogoMark mono className="size-6" />
          <div>
            <p className="text-xs font-bold tracking-[0.08em]">ONEA</p>
            <p className="text-[11px]">{fr.print.organisation}</p>
          </div>
        </div>
        <dl className="text-right text-[11px] tabular-nums">
          <dt className="sr-only">{fr.print.reference}</dt>
          <dd className="font-semibold">{reference}</dd>
          {documentType && <dd>{documentType}</dd>}
          {(version || status) && <dd>{[version, status].filter(Boolean).join(" · ")}</dd>}
        </dl>
      </header>

      <main className="py-6 print:py-0">{children}</main>

      <footer className="flex items-center justify-between gap-4 border-t border-border pt-2 text-[10px] print:fixed print:right-0 print:bottom-0 print:left-0 print:bg-surface">
        <span className="font-semibold uppercase">{fr.print.confidential}</span>
        {printedAt && printedBy && (
          <span>
            {fr.print.printedOn} {printedAt} {fr.print.by} {printedBy}
          </span>
        )}
      </footer>
    </div>
  );
}
