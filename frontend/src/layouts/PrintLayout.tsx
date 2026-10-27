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
 * Gabarit d'impression A4 (noir sur blanc). Marges et pagination « Page N sur M » : `@page`
 * dans globals.css. L'en-tête et le pied sont les groupes `thead` / `tfoot` d'un tableau de
 * mise en page : le navigateur les répète sur chaque page en réservant leur hauteur, sans
 * jamais recouvrir le contenu. Ce composant n'est pas un repère `main` (le shell le fournit).
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
      <table role="presentation" className="w-full border-collapse">
        <thead>
          <tr>
            <td className="pb-6 print:pb-4">
              <header className="flex items-start justify-between gap-6 border-b border-foreground pb-3">
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
            </td>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>{children}</td>
          </tr>
        </tbody>
        <tfoot>
          <tr>
            <td className="pt-6 print:pt-4">
              <footer className="flex items-center justify-between gap-4 border-t border-border pt-2 text-[10px]">
                <span className="font-semibold uppercase">{fr.print.confidential}</span>
                {printedAt && printedBy && (
                  <span>
                    {fr.print.printedOn} {printedAt} {fr.print.by} {printedBy}
                  </span>
                )}
              </footer>
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
