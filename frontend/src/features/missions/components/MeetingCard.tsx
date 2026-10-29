import { useState } from "react";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import { formatDate, formatDateTime } from "@/lib/dates";
import { useMarkMeetingHeld } from "../api";
import { TYPE_REUNION_LABELS } from "../labels";
import type { Mission, Reunion, TypeReunion } from "../types";
import { ConfirmActionDialog } from "./ConfirmActionDialog";
import { MeetingFormDialog } from "./MeetingFormDialog";

const t = fr.missionTravaux;

type Props = {
  mission: Mission;
  type: TypeReunion;
  meeting?: Reunion;
  /** Étape clôturée : même sans réunion enregistrée, la carte reste en lecture seule. */
  stepClosed?: boolean;
};

function Row({ label, children }: { label: string; children: string }) {
  return (
    <div className="grid gap-0.5 sm:grid-cols-[10rem_minmax(0,1fr)] sm:gap-3">
      <dt className="text-text-muted">{label}</dt>
      <dd className="whitespace-pre-line">{children || t.notProvided}</dd>
    </div>
  );
}

/** Carte d'une réunion (ouverture, lancement ou clôture). Droits lus sur le serveur uniquement. */
export function MeetingCard({ mission, type, meeting, stepClosed = false }: Props) {
  const [formOpen, setFormOpen] = useState(false);
  const [heldOpen, setHeldOpen] = useState(false);
  const markHeld = useMarkMeetingHeld();
  const titleId = `meeting-${type}`;
  const closed = stepClosed || meeting?.etape_close === true;
  const canWrite = mission.mes_droits.contribuer && !closed;

  const participants = [
    ...(meeting?.participants_detail ?? []).map((u) => u.nom_complet),
    ...(meeting?.participants_externes ?? "").split("\n").filter((l) => l.trim() !== ""),
  ];

  return (
    <section aria-labelledby={titleId} className="rounded-md border border-border p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 id={titleId} className="text-base font-semibold">
          {TYPE_REUNION_LABELS[type]}
        </h3>
        {meeting && (
          <span className="text-sm text-text-muted">
            {meeting.tenue_le
              ? t.statusHeld.replace("{date}", formatDate(meeting.tenue_le))
              : t.statusPlanned}
          </span>
        )}
      </div>

      {meeting ? (
        <dl className="grid gap-2 text-sm">
          <Row label={t.meetingDate}>{formatDateTime(meeting.date)}</Row>
          <Row label={t.meetingPlace}>{meeting.lieu ?? ""}</Row>
          <Row label={t.meetingParticipants}>{participants.join("\n")}</Row>
          <Row label={t.meetingAgenda}>{meeting.ordre_du_jour ?? ""}</Row>
          <Row label={t.meetingDecisions}>{meeting.decisions ?? ""}</Row>
          <Row label={t.meetingMinutes}>{meeting.compte_rendu ?? ""}</Row>
        </dl>
      ) : (
        <p className="text-sm text-text-muted">{t.noMeeting}</p>
      )}

      {closed && <p className="mt-3 text-sm text-text-muted">{t.readOnlyClosed}</p>}

      {/* LOT4-SLOT: le lot 4 remplace cette mention par le document PV généré. */}
      <p className="mt-3 text-sm text-text-muted" data-slot="lot4-pv">
        {t.pvLater}
      </p>

      {canWrite && (
        <div className="mt-4 flex flex-wrap gap-2 print:hidden">
          {meeting ? (
            <>
              <Button type="button" variant="outline" onClick={() => setFormOpen(true)}>
                {t.editMeeting}
              </Button>
              {!meeting.tenue_le && (
                <Button type="button" onClick={() => setHeldOpen(true)}>
                  {t.markHeld}
                </Button>
              )}
            </>
          ) : (
            <Button type="button" onClick={() => setFormOpen(true)}>
              {t.planMeeting}
            </Button>
          )}
        </div>
      )}

      {canWrite && formOpen && (
        <MeetingFormDialog
          open
          onOpenChange={setFormOpen}
          mission={mission}
          type={type}
          meeting={meeting}
        />
      )}
      {canWrite && meeting && (
        <ConfirmActionDialog
          open={heldOpen}
          onOpenChange={setHeldOpen}
          title={t.markHeldTitle}
          text={t.markHeldText}
          confirmLabel={t.markHeld}
          onConfirm={() => markHeld.mutateAsync(meeting.id)}
        />
      )}
    </section>
  );
}
