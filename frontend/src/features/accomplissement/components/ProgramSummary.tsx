import { ALERT_CLASS } from "@/components/form/FormField";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatDays } from "@/features/missions/format";
import { fr } from "@/i18n/fr";
import { useProgramSummary } from "../api";

const t = fr.programme;

/** Synthèse du programme : charges par objectif et par auditeur, total et budget de la mission. */
export function ProgramSummary({ missionId }: { missionId: string }) {
  const summary = useProgramSummary(missionId);

  if (summary.isPending) {
    return (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  }
  if (summary.isError) {
    return (
      <p role="alert" className={ALERT_CLASS}>
        {t.loadError}
      </p>
    );
  }

  const s = summary.data;
  const budget = Number(s.budget_jours);
  const hasBudget = s.budget_jours !== null && !Number.isNaN(budget) && budget > 0;
  const totals = (hasBudget ? t.totals : t.totalsNoBudget)
    .replace("{total}", formatDays(s.total_charge))
    .replace("{budget}", formatDays(s.budget_jours));
  const excess = formatDays(String(Math.round((Number(s.total_charge) - budget) * 100) / 100));

  return (
    <section aria-labelledby={`summary-${missionId}`} className="grid gap-3">
      <h4 id={`summary-${missionId}`} className="font-semibold">
        {t.summaryTitle}
      </h4>
      <div className="grid gap-4 lg:grid-cols-2">
        <Table aria-label={t.byObjectiveCaption}>
          <TableHeader>
            <TableRow>
              <TableHead>{t.colObjective}</TableHead>
              <TableHead className="text-right">{t.colTests}</TableHead>
              <TableHead className="text-right">{t.colLoadShort}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {s.objectifs.map((o) => (
              <TableRow key={o.code}>
                <TableCell>
                  <span className="font-medium">{o.code}</span> {o.libelle}
                </TableCell>
                <TableCell className="text-right">{o.nb_tests}</TableCell>
                <TableCell className="text-right">{formatDays(o.charge)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <Table aria-label={t.byAuditorCaption}>
          <TableHeader>
            <TableRow>
              <TableHead>{t.colAuditor}</TableHead>
              <TableHead className="text-right">{t.colTests}</TableHead>
              <TableHead className="text-right">{t.colLoadShort}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {s.auditeurs.length === 0 ? (
              <TableRow>
                <TableCell colSpan={3} className="text-text-muted">
                  {t.noAuditors}
                </TableCell>
              </TableRow>
            ) : (
              s.auditeurs.map((a) => (
                <TableRow key={a.utilisateur.id}>
                  <TableCell>{a.utilisateur.nom_complet}</TableCell>
                  <TableCell className="text-right">{a.nb_tests}</TableCell>
                  <TableCell className="text-right">{formatDays(a.charge)}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
      <p className="text-sm font-medium">{totals}</p>
      {s.depassement_budget && (
        <p
          role="status"
          className="rounded-md border border-warning/50 bg-surface-subtle p-3 text-sm"
        >
          {t.overBudget.replace("{excess}", excess)}
        </p>
      )}
      {s.tests_sans_auditeur.length > 0 && (
        <p className="text-sm text-text-muted">
          {t.withoutAuditor.replace("{codes}", s.tests_sans_auditeur.join(", "))}
        </p>
      )}
    </section>
  );
}
