import { fr } from "@/i18n/fr";
import { formatDateTime } from "@/lib/dates";
import type { Rapport } from "../types";

const t = fr.rapportFinal;

/** Évènements du rapport (création, soumission, validation, renvoi, diffusion, correction). */
export function ReportJournal({ evenements }: { evenements: Rapport["evenements"] }) {
  return (
    <section aria-labelledby="report-journal-title" className="grid gap-2">
      <h3 id="report-journal-title" className="text-base font-semibold">
        {t.journalTitle}
      </h3>
      {evenements.length === 0 ? (
        <p className="text-sm text-text-muted">{t.journalEmpty}</p>
      ) : (
        <table className="w-full text-sm">
          <caption className="sr-only">{t.journalCaption}</caption>
          <thead>
            <tr className="border-b border-border text-left">
              <th scope="col" className="py-1 pr-3">
                {t.journalDate}
              </th>
              <th scope="col" className="py-1 pr-3">
                {t.journalEvent}
              </th>
              <th scope="col" className="py-1 pr-3">
                {t.journalBy}
              </th>
              <th scope="col" className="py-1">
                {t.journalMotif}
              </th>
            </tr>
          </thead>
          <tbody>
            {evenements.map((e) => (
              <tr key={e.id} className="border-b border-border align-top">
                <td className="py-1 pr-3 tabular-nums">{formatDateTime(e.le)}</td>
                <td className="py-1 pr-3">{t.events[e.type]}</td>
                <td className="py-1 pr-3">{e.par.nom_complet}</td>
                <td className="py-1 whitespace-pre-line">{e.motif}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
