import type { ReactNode } from "react";
import { ALERT_CLASS } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import { useMeetings } from "@/features/missions/api";
import { MeetingCard } from "@/features/missions/components/MeetingCard";
import type { ZoneProps } from "@/features/missions/zones";
import { fr } from "@/i18n/fr";
import { formatDate } from "@/lib/dates";
import { useCreateReport, useDraftReports, useDraftResponses, useMissionReport } from "../api";
import { ClosingFindingsPanel } from "../components/ClosingFindingsPanel";
import { DocumentSlot } from "../components/DocumentSlot";
import { DraftResponsesTable } from "../components/DraftResponsesTable";
import { TransmitDraftDialog } from "../components/TransmitDraftDialog";
import { latestDraft } from "../draftQueries";
import type { RapportProvisoire } from "../types";

const t = fr.rapportProvisoire;

type QueryLike = { isPending: boolean; isError: boolean; refetch: () => unknown };

/** Chargement ou erreur (avec « Réessayer ») ; jamais rendus comme un état vide. */
function Loaded({ query, children }: { query: QueryLike; children: ReactNode }) {
  if (query.isError) {
    return (
      <div role="alert" className={`${ALERT_CLASS} flex flex-wrap items-center gap-3`}>
        <span>{t.loadError}</span>
        <Button type="button" variant="outline" size="sm" onClick={() => void query.refetch()}>
          {fr.common.retry}
        </Button>
      </div>
    );
  }
  if (query.isPending) {
    return (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  }
  return <>{children}</>;
}

function DraftSection({ draft }: { draft: RapportProvisoire }) {
  const responses = useDraftResponses({ provisoire: draft.id });
  return (
    <section aria-labelledby="draft-sent" className="grid gap-3">
      <h3 id="draft-sent" className="text-base font-semibold">
        {t.draftTitle}
      </h3>
      <p className="text-sm" role="status">
        {t.draftTransmitted
          .replace("{date}", formatDate(draft.transmis_le))
          .replace("{limite}", formatDate(draft.date_limite_reponses))}
      </p>
      <DocumentSlot
        typeDocument="RAPPORT_PROVISOIRE"
        objetId={draft.id}
        missionId={draft.mission}
      />
      <h4 className="text-sm font-semibold">{t.responsesTitle}</h4>
      <Loaded query={responses}>
        <DraftResponsesTable provisoire={draft} responses={responses.data?.results ?? []} />
      </Loaded>
    </section>
  );
}

/** Étape XV : réunion de clôture, constats à présenter, transmission du rapport provisoire. */
export function StepXVZone({ mission, step }: ZoneProps) {
  const id = `zone-XV-${step.id}`;
  const meetings = useMeetings(mission.id);
  const report = useMissionReport(mission.id);
  const drafts = useDraftReports(report.data?.id);
  const createReport = useCreateReport();
  const stepClosed = step.statut === "VALIDEE" || step.statut === "NON_APPLICABLE";
  const canWrite = mission.mes_droits.contribuer && !stepClosed;
  const closing = meetings.data?.results.find((m) => m.type === "CLOTURE");
  const rapport = report.data;
  const draft = latestDraft(drafts.data?.results ?? []);

  let transmission: ReactNode;
  if (report.isError || report.isPending) {
    transmission = <Loaded query={report}>{null}</Loaded>;
  } else if (rapport === null || rapport === undefined) {
    transmission = (
      <div className="grid gap-2">
        <p className="text-sm text-text-muted">{t.noReport}</p>
        {canWrite && (
          <div>
            <Button
              type="button"
              variant="outline"
              disabled={createReport.isPending}
              onClick={() => createReport.mutate({ missionId: mission.id })}
            >
              {t.createReport}
            </Button>
          </div>
        )}
        {createReport.isError && (
          <p role="alert" className={ALERT_CLASS}>
            {createReport.error.message}
          </p>
        )}
      </div>
    );
  } else {
    transmission = (
      <Loaded query={drafts}>
        {draft ? (
          <DraftSection draft={draft} />
        ) : (
          canWrite &&
          rapport.actions_possibles.includes("TRANSMETTRE") && (
            <div>
              <TransmitDraftDialog rapportId={rapport.id} missionId={mission.id} />
            </div>
          )
        )}
      </Loaded>
    );
  }

  return (
    <section aria-labelledby={id} className="grid gap-6">
      <h2 id={id} className="text-base font-semibold">
        {fr.communication.zoneXVTitle}
      </h2>
      <Loaded query={meetings}>
        <MeetingCard mission={mission} type="CLOTURE" meeting={closing} stepClosed={stepClosed} />
        {closing && (
          <section aria-labelledby="pv-cloture" className="grid gap-2">
            <h3 id="pv-cloture" className="text-base font-semibold">
              {t.pvTitle}
            </h3>
            <DocumentSlot typeDocument="PV_CLOTURE" objetId={closing.id} missionId={mission.id} />
          </section>
        )}
      </Loaded>
      <ClosingFindingsPanel missionId={mission.id} />
      {transmission}
    </section>
  );
}
