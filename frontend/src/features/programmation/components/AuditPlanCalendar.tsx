import { fr } from "@/i18n/fr";
import { MONTH_LABELS } from "../labels";
import type { AuditPlanLine } from "../types";

const s = fr.programmationLignes;

/** Année et mois (0-11) d'une date ISO « AAAA-MM-JJ ». */
function ym(date: string): { y: number; m: number } {
  return { y: Number(date.slice(0, 4)), m: Number(date.slice(5, 7)) - 1 };
}

/**
 * Calendrier annuel des missions prévues : une ligne par mission, un mois par colonne.
 * Un mois couvert est rempli (couleur) et porte aussi un repère visible et un texte accessible.
 */
export function AuditPlanCalendar({ year, lines }: { year: number; lines: AuditPlanLine[] }) {
  return (
    // Région défilable : le focus clavier permet de la faire défiler à la flèche.
    <div
      role="region"
      aria-label={s.calendarRegion}
      // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
      tabIndex={0}
      className="overflow-x-auto rounded-lg border border-border bg-surface print:overflow-visible print:border-0"
    >
      <style>{"@media print { @page { size: landscape; } }"}</style>
      <table className="w-full min-w-[960px] border-collapse text-sm print:min-w-0 print:text-xs">
        <caption className="p-3 text-left text-base font-semibold">
          {s.calendarCaption.replace("{annee}", String(year))}
        </caption>
        <thead>
          <tr className="border-y border-border bg-surface-subtle">
            <th scope="col" className="px-3 py-2 text-left font-semibold">
              {s.calendarMission}
            </th>
            {MONTH_LABELS.map((label) => (
              <th key={label} scope="col" className="px-1 py-2 text-center font-semibold">
                {label}
              </th>
            ))}
            <th scope="col" className="px-3 py-2 text-left font-semibold">
              {s.calendarBeyond}
            </th>
          </tr>
        </thead>
        <tbody>
          {lines.length === 0 && (
            <tr>
              <td colSpan={14} className="px-3 py-4 text-text-muted">
                {s.calendarEmpty}
              </td>
            </tr>
          )}
          {lines.map((line) => {
            const start = ym(line.debut_prevu);
            const end = ym(line.fin_prevue);
            const from = start.y < year ? 0 : start.y === year ? start.m : 12;
            const to = end.y < year ? -1 : end.y === year ? end.m : 11;
            return (
              <tr key={line.id} className="border-b border-border last:border-b-0">
                <th scope="row" className="px-3 py-2 text-left font-medium">
                  <span className="tabular-nums">
                    {fr.programmation.number} {line.numero}
                  </span>
                  {" - "}
                  {line.titre}
                </th>
                {MONTH_LABELS.map((label, m) => {
                  const covered = m >= from && m <= to;
                  return (
                    <td
                      key={label}
                      className={`h-9 border-l border-border text-center ${
                        covered ? "bg-primary/25 print:bg-primary/25" : ""
                      }`}
                    >
                      {covered && (
                        <>
                          <span aria-hidden className="font-bold text-primary">
                            ■
                          </span>
                          <span className="sr-only">{s.calendarPlanned}</span>
                        </>
                      )}
                    </td>
                  );
                })}
                <td className="border-l border-border px-3 py-2 tabular-nums">
                  {end.y > year ? `→ ${MONTH_LABELS[end.m]} ${end.y}` : ""}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
