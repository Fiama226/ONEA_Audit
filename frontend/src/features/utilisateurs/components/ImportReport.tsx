import { useEffect, useRef } from "react";
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
  const headingRef = useRef<HTMLHeadingElement>(null);
  // Le résultat remplace des boutons qui disparaissent : le focus va sur le titre du rapport.
  useEffect(() => {
    headingRef.current?.focus();
  }, [report]);
  const summary = [
    plural(report.crees.length, t.createdOne, t.createdMany),
    plural(report.ignores.length, t.ignoredOne, t.ignoredMany),
  ].join(", ");
  return (
    <section
      className="grid gap-3"
      aria-label={report.dry_run ? t.reportDryRunTitle : t.reportDoneTitle}
    >
      <h3 ref={headingRef} tabIndex={-1} className="text-base font-semibold outline-none">
        {report.dry_run ? t.reportDryRunTitle : t.reportDoneTitle}
      </h3>
      <p role="status" className="text-sm">
        {summary}
      </p>
      <NameList title={t.createdList} items={report.crees} />
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
                <TableRow key={`${row.ligne}-${row.identifiant}-${i}`}>
                  <TableCell>{row.ligne}</TableCell>
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
