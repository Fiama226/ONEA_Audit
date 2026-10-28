import { Link } from "react-router-dom";
import { fr } from "@/i18n/fr";
import { formatDate } from "@/lib/dates";
import { formatDays } from "../format";
import { INTERVENTION_TYPE_LABELS, quarterLabel } from "../labels";
import type { AuditPlanLine } from "../types";

const c = fr.programmationPlans;
const p = fr.programmation;

function countLabel(n: number): string {
  return n === 1 ? c.lineOne : c.lineMany.replace("{n}", String(n));
}

function withDeleted(label: string, deleted: boolean): string {
  return deleted ? `${label} ${p.deleted}` : label;
}

/** Regroupe par trimestre, dans l'ordre chronologique, puis par date de début et numéro. */
export function groupByQuarter(lines: AuditPlanLine[]): [number, AuditPlanLine[]][] {
  const groups = new Map<number, AuditPlanLine[]>();
  for (const line of lines) {
    groups.set(line.trimestre, [...(groups.get(line.trimestre) ?? []), line]);
  }
  return [...groups.entries()]
    .sort(([a], [b]) => a - b)
    .map(([q, rows]) => [
      q,
      [...rows].sort((x, y) => x.debut_prevu.localeCompare(y.debut_prevu) || x.numero - y.numero),
    ]);
}

const TH = "sticky top-0 bg-surface px-2 py-2 text-left text-xs font-medium text-text-muted";

/** Tableau sémantique des missions prévues, un `<tbody>` par trimestre. */
export function PlanLinesTable({ lines }: { lines: AuditPlanLine[] }) {
  const groups = groupByQuarter(lines);
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-surface">
      <table className="w-full text-sm tabular-nums">
        <caption className="sr-only">{c.linesCaption}</caption>
        <thead>
          <tr className="border-b border-border">
            <th scope="col" className={TH}>
              {p.number}
            </th>
            <th scope="col" className={TH}>
              {p.line}
            </th>
            <th scope="col" className={TH}>
              {p.type}
            </th>
            <th scope="col" className={TH}>
              {p.process}
            </th>
            <th scope="col" className={TH}>
              {p.auditableObject}
            </th>
            <th scope="col" className={TH}>
              {p.entities}
            </th>
            <th scope="col" className={TH}>
              {p.plannedStart}
            </th>
            <th scope="col" className={TH}>
              {p.plannedEnd}
            </th>
            <th scope="col" className={`${TH} text-right`}>
              {c.loadColumn}
            </th>
          </tr>
        </thead>
        {groups.map(([quarter, rows]) => (
          <tbody key={quarter} className="break-inside-avoid">
            <tr className="bg-surface-subtle">
              <th
                scope="colgroup"
                colSpan={9}
                className="px-2 py-2 text-left text-sm font-semibold"
              >
                {c.groupHeader
                  .replace("{quarter}", quarterLabel(quarter))
                  .replace("{count}", countLabel(rows.length))}
              </th>
            </tr>
            {rows.map((line) => (
              <tr key={line.id} className="border-b border-border last:border-0 align-top">
                <td className="px-2 py-2">{line.numero}</td>
                <td className="px-2 py-2">
                  <Link
                    to={`/programme-annuel/lignes/${line.id}`}
                    className="font-medium text-primary underline-offset-4 hover:underline"
                  >
                    {line.titre}
                  </Link>
                </td>
                <td className="px-2 py-2">{INTERVENTION_TYPE_LABELS[line.type]}</td>
                <td className="px-2 py-2">
                  {withDeleted(
                    `${line.processus_code} - ${line.processus_libelle}`,
                    line.processus_supprime,
                  )}
                </td>
                <td className="px-2 py-2">
                  {line.objet_auditable_libelle
                    ? withDeleted(line.objet_auditable_libelle, line.objet_auditable_supprime)
                    : c.noValue}
                </td>
                <td className="px-2 py-2">
                  {line.entites_detail.length === 0
                    ? c.noValue
                    : line.entites_detail.map((e) => withDeleted(e.code, e.supprime)).join(", ")}
                </td>
                <td className="px-2 py-2 whitespace-nowrap">{formatDate(line.debut_prevu)}</td>
                <td className="px-2 py-2 whitespace-nowrap">{formatDate(line.fin_prevue)}</td>
                <td className="px-2 py-2 text-right">
                  {formatDays(line.charge_prevue_jours ?? 0)}
                </td>
              </tr>
            ))}
          </tbody>
        ))}
      </table>
    </div>
  );
}
