import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { fr } from "@/i18n/fr";
import type { RapportImport } from "../types";

const t = fr.utilisateurs.import;

/** « 1 compte créé », « 2 comptes créés » : le zéro s'accorde au singulier. */
function plural(n: number, singular: string, pluralForm: string): string {
  return `${n} ${n > 1 ? pluralForm : singular}`;
}

function NameList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div className="grid gap-1">
      <h4 className="text-sm font-semibold">{title}</h4>
      <ul className="list-disc pl-5 text-sm">
        {items.map((item, i) => (
          <li key={`${item}-${i}`}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

/** Rapport d'import (vérification à blanc ou import réel) avec le motif de chaque ligne ignorée. */
export function ImportReport({ report }: { report: RapportImport }) {
  const summary = [
    `${plural(report.crees.length, `compte ${t.created}`, `comptes ${t.created}s`)}`,
    `${report.mis_a_jour.length} ${t.updated}`,
    `${plural(report.ignores.length, `${t.line} ${t.ignored}`, `${t.line}s ${t.ignored}s`)}`,
  ].join(", ");
  return (
    <section
      className="grid gap-3"
      aria-label={report.dry_run ? t.reportDryRunTitle : t.reportDoneTitle}
    >
      <h3 className="text-base font-semibold">
        {report.dry_run ? t.reportDryRunTitle : t.reportDoneTitle}
      </h3>
      <p className="text-sm">{summary}</p>
      <NameList title={t.createdList} items={report.crees} />
      <NameList title={t.updatedList} items={report.mis_a_jour} />
      {report.ignores.length > 0 && (
        <div className="max-h-64 overflow-auto rounded-md border border-border">
          <Table>
            <TableCaption className="sr-only">{t.ignoredCaption}</TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead scope="col">{t.colLine}</TableHead>
                <TableHead scope="col">{t.colIdentifier}</TableHead>
                <TableHead scope="col">{t.colReason}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {report.ignores.map((row, i) => (
                <TableRow key={`${row.ligne ?? "x"}-${row.identifiant}-${i}`}>
                  <TableCell>{row.ligne ?? t.noLine}</TableCell>
                  <TableCell>{row.identifiant}</TableCell>
                  <TableCell className="whitespace-normal">{row.motif}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </section>
  );
}
