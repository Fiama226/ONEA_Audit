import { formatDateTime } from "@/lib/dates";
import { fr } from "@/i18n/fr";
import type { FicheDetail } from "../types";

const t = fr.fiches;

/** Journal des transitions de la fiche (qui, quand, motif). */
export function SheetJournal({ evenements }: { evenements: FicheDetail["evenements"] }) {
  return (
    <section aria-labelledby="fiche-journal" className="grid gap-2">
      <h3 id="fiche-journal" className="text-base font-semibold">
        {t.journalTitle}
      </h3>
      {evenements.length === 0 ? (
        <p className="text-sm text-text-muted">{t.journalEmpty}</p>
      ) : (
        <ol className="grid gap-2 text-sm">
          {evenements.map((event) => (
            <li key={event.id} className="rounded-md border border-border p-2">
              <p>
                <strong>{t.journalEvents[event.type] ?? event.type}</strong> {t.journalBy}{" "}
                {event.par.nom_complet} · {formatDateTime(event.le)}
              </p>
              {event.motif && (
                <p className="text-text-muted">
                  {t.journalReason} : {event.motif}
                </p>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
