import { fr } from "@/i18n/fr";
import { formatDateTime } from "@/lib/dates";
import { TYPE_EVENEMENT_ETAPE_LABELS } from "../labels";
import type { Etape } from "../types";

const m = fr.missionEtapes;

/** Journal des événements d'une étape (ajout seul côté serveur). */
export function StepJournal({ step }: { step: Etape }) {
  const id = `journal-${step.id}`;
  return (
    <section aria-labelledby={id} className="grid gap-2">
      <h3 id={id} className="text-base font-semibold">
        {m.journalTitle}
      </h3>
      {step.evenements.length === 0 ? (
        <p className="text-sm text-text-muted">{m.journalEmpty}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border text-text-muted">
                <th scope="col" className="py-1 pr-3 font-medium">
                  {m.colDateTime}
                </th>
                <th scope="col" className="py-1 pr-3 font-medium">
                  {m.colAuthor}
                </th>
                <th scope="col" className="py-1 pr-3 font-medium">
                  {m.colAction}
                </th>
                <th scope="col" className="py-1 font-medium">
                  {m.colMotif}
                </th>
              </tr>
            </thead>
            <tbody>
              {step.evenements.map((e, i) => (
                <tr key={`${i}-${e.le}-${e.type}`} className="border-b border-border/60 align-top">
                  <td className="py-1 pr-3 tabular-nums">{formatDateTime(e.le)}</td>
                  <td className="py-1 pr-3">{e.par.nom_complet}</td>
                  <td className="py-1 pr-3">{TYPE_EVENEMENT_ETAPE_LABELS[e.type]}</td>
                  <td className="py-1">{e.motif || m.noValue}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
