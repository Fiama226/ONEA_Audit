import { ALERT_CLASS } from "@/components/form/FormField";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { STATUT_ETAPE_LABELS } from "@/features/missions/labels";
import { fr } from "@/i18n/fr";
import { formatDate } from "@/lib/dates";
import { STATUT_REFERENTIEL_LABELS, TYPE_AVIS_LABELS } from "../labels";
import { Heading, type HeadingLevel } from "./Heading";
import type { ReferentielAudit } from "../types";

const t = fr.analyseVVI;

/** Empreinte raccourcie « 3f2a…9c1b » pour l'affichage. */
function shortHash(hash: string): string {
  return hash.length > 12 ? `${hash.slice(0, 4)}…${hash.slice(-4)}` : hash;
}

/** Synthèse du référentiel : statut, avancement, validation (empreinte) et avis des audités. */
export function FrameworkStatusPanel({
  framework,
  level = 3,
}: {
  framework: ReferentielAudit;
  level?: HeadingLevel;
}) {
  const v = framework.validation;
  const validation = v && {
    date: formatDate(v.confirme_le),
    name: v.signataire.nom_complet,
    hash: shortHash(v.empreinte),
  };
  const stats: [string, string][] = [
    [t.statusLabel, STATUT_REFERENTIEL_LABELS[framework.statut]],
    [t.stepVLabel, STATUT_ETAPE_LABELS[framework.statut_v]],
    [t.stepVILabel, STATUT_ETAPE_LABELS[framework.statut_vi]],
    [t.linesLabel, String(framework.nb_lignes)],
    [t.strengthsLabel, String(framework.nb_forces)],
    [t.weaknessesLabel, String(framework.nb_faiblesses)],
  ];

  return (
    <section aria-labelledby="framework-status-title" className="grid gap-3">
      <Heading level={level} id="framework-status-title" className="text-base font-semibold">
        {t.statusPanelTitle}
      </Heading>
      <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3 lg:grid-cols-6">
        {stats.map(([label, value]) => (
          <div key={label} className="rounded-md border border-border p-3">
            <dt className="text-xs text-text-muted">{label}</dt>
            <dd className="font-medium">{value}</dd>
          </div>
        ))}
      </dl>
      {validation ? (
        framework.validation_verifiee ? (
          <p className="text-sm">
            {t.validatedBy
              .replace("{date}", validation.date)
              .replace("{name}", validation.name)
              .replace("{hash}", validation.hash)}
          </p>
        ) : (
          <div role="alert" className={ALERT_CLASS}>
            <p className="font-medium">{t.unverified}</p>
            <p>
              {t.unverifiedText
                .replace("{date}", validation.date)
                .replace("{name}", validation.name)
                .replace("{hash}", validation.hash)}
            </p>
          </div>
        )
      ) : (
        <p className="text-sm text-text-muted">{t.notValidated}</p>
      )}
      <Heading level={(level + 1) as HeadingLevel} className="text-sm font-semibold">
        {t.opinionsTitle}
      </Heading>
      {framework.avis.length === 0 ? (
        <p className="text-sm text-text-muted">{t.noOpinion}</p>
      ) : (
        <div className="overflow-hidden rounded-md border border-border">
          <Table aria-label={t.opinionsTitle}>
            <TableHeader>
              <TableRow>
                <TableHead>{t.colDate}</TableHead>
                <TableHead>{t.colAuthor}</TableHead>
                <TableHead>{t.colOpinion}</TableHead>
                <TableHead>{t.colComment}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {framework.avis.map((a) => (
                <TableRow key={a.id}>
                  <TableCell>{formatDate(a.donne_le)}</TableCell>
                  <TableCell>{a.auteur.nom_complet}</TableCell>
                  <TableCell>{TYPE_AVIS_LABELS[a.avis]}</TableCell>
                  <TableCell className="whitespace-normal">{a.commentaire || "—"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </section>
  );
}
