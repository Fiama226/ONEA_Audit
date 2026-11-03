import { Printer } from "lucide-react";
import { useParams } from "react-router-dom";
import { PrintLayout } from "@/components/print/PrintLayout";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import { formatDate, formatDateTime } from "@/lib/dates";
import { useTracking } from "../api";
import { StepStatusBadge } from "../components/StepStatusBadge";
import { formatDays, formatGap } from "../format";
import { PHASE_LABELS, PHASE_ORDER, PHASE_RANGES, TYPE_EVENEMENT_ETAPE_LABELS } from "../labels";
import { ScrollRegion } from "@/components/ui/scroll-region";

const m = fr.missionEtapes;

function date(value: string | null): string {
  return value ? formatDate(value) : m.noValue;
}

const HEADS = [
  m.colStep,
  m.colStatus,
  m.colPlannedStart,
  m.colPlannedEnd,
  m.colActualStart,
  m.colActualEnd,
  m.colGap,
  m.colPlannedCharge,
  m.colActualCharge,
];

/** Fiche de suivi de la mission : budget, étapes par phase et journal chronologique. */
export function TrackingPage() {
  const { id } = useParams();
  const tracking = useTracking(id);

  if (tracking.isError) {
    return (
      <p role="alert" className="text-sm text-destructive">
        {m.trackingLoadError}
      </p>
    );
  }
  if (!tracking.data) {
    return (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  }
  const { data } = tracking;

  return (
    <PrintLayout
      title={m.printHeader.replace("{reference}", data.mission.reference)}
      reference={data.mission.reference}
      orientation="paysage"
    >
      <section aria-labelledby="tracking-title" className="grid gap-6">
        <p className="hidden text-sm print:block">{data.mission.titre}</p>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="tracking-title" className="text-lg font-semibold">
            {fr.missions.tabTracking}
          </h2>
          <Button
            type="button"
            variant="outline"
            className="print:hidden"
            onClick={() => window.print()}
          >
            <Printer aria-hidden />
            {m.printSheet}
          </Button>
        </div>
        <p className="text-sm">
          {m.budgetLine
            .replace("{budget}", `${formatDays(data.budget_jours)} j`)
            .replace("{prevu}", `${formatDays(data.total_prevu)} j`)
            .replace("{reel}", `${formatDays(data.total_reel)} j`)}
        </p>

        <ScrollRegion label={m.trackingCaption}>
          <table className="w-full text-left text-sm">
            <caption className="sr-only">{m.trackingCaption}</caption>
            <thead>
              <tr className="border-b border-border text-text-muted">
                {HEADS.map((h) => (
                  <th key={h} scope="col" className="px-2 py-1 font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            {PHASE_ORDER.map((phase) => (
              <tbody key={phase}>
                <tr className="bg-surface-subtle">
                  <th
                    scope="rowgroup"
                    colSpan={HEADS.length}
                    className="px-2 py-1 text-left font-semibold"
                  >
                    {PHASE_LABELS[phase]}{" "}
                    {fr.missions.stepRange.replace("{range}", PHASE_RANGES[phase])}
                  </th>
                </tr>
                {data.lignes
                  .filter((l) => l.phase === phase)
                  .map((l) => (
                    <tr
                      key={l.numero}
                      className="break-inside-avoid border-b border-border/60 align-top"
                    >
                      <th scope="row" className="px-2 py-1 font-medium">
                        {l.romain} · {l.titre}
                      </th>
                      <td className="px-2 py-1">
                        <StepStatusBadge statut={l.statut} />
                      </td>
                      <td className="px-2 py-1 tabular-nums">{date(l.debut_prevu)}</td>
                      <td className="px-2 py-1 tabular-nums">{date(l.fin_prevue)}</td>
                      <td className="px-2 py-1 tabular-nums">{date(l.debut_reel)}</td>
                      <td className="px-2 py-1 tabular-nums">{date(l.fin_reelle)}</td>
                      <td className="px-2 py-1">{formatGap(l.ecart_jours)}</td>
                      <td className="px-2 py-1 tabular-nums">{formatDays(l.charge_prevue)}</td>
                      <td className="px-2 py-1 tabular-nums">{formatDays(l.charge_reelle)}</td>
                    </tr>
                  ))}
              </tbody>
            ))}
          </table>
        </ScrollRegion>

        <section aria-labelledby="tracking-journal" className="grid gap-2">
          <h3 id="tracking-journal" className="text-base font-semibold">
            {m.trackingJournal}
          </h3>
          {data.evenements.length === 0 ? (
            <p className="text-sm text-text-muted">{m.trackingJournalEmpty}</p>
          ) : (
            <ol className="grid gap-1 text-sm">
              {data.evenements.map((e, i) => (
                <li key={`${i}-${e.le}-${e.etape_romain}-${e.type}`} className="break-inside-avoid">
                  <span className="tabular-nums text-text-muted">{formatDateTime(e.le)}</span> ·{" "}
                  {e.par.nom_complet} · {fr.missions.stepPrefix} {e.etape_romain} ·{" "}
                  {TYPE_EVENEMENT_ETAPE_LABELS[e.type]}
                  {e.motif && <> — {e.motif}</>}
                </li>
              ))}
            </ol>
          )}
        </section>
      </section>
    </PrintLayout>
  );
}
