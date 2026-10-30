import { useState } from "react";
import { useParams } from "react-router-dom";
import { ALERT_CLASS } from "@/components/form/FormField";
import { StatusPill } from "@/components/StatusPill";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import { formatDate, formatDateTime } from "@/lib/dates";
import { useDraftResponses } from "../api";
import { DocumentSlot } from "../components/DocumentSlot";
import { DraftResponseDialog } from "../components/DraftResponseDialog";
import { latestDraft, useMissionDrafts } from "../draftQueries";
import type { ConstatProvisoire, RapportProvisoire } from "../types";

const t = fr.rapportProvisoire;
const DAY_MS = 86_400_000;

/** Jours restants jusqu'à la date limite (jour inclus), dans le fuseau de l'application. */
function daysLeft(limit: string, now: Date = new Date()): number {
  const [d = "", m = "", y = ""] = formatDate(now.toISOString()).split("/");
  const today = Date.UTC(Number(y), Number(m) - 1, Number(d));
  return Math.round((Date.parse(`${limit}T00:00:00Z`) - today) / DAY_MS);
}

function DeadlineAlert({ limit }: { limit: string }) {
  const days = daysLeft(limit);
  let message: string;
  if (days < 0) message = t.deadlinePassed;
  else if (days === 0) message = t.deadlineToday;
  else if (days === 1) message = t.deadlineOneDay;
  else message = t.deadlineDays.replace("{count}", String(days));
  return (
    <div
      role="status"
      className={`rounded-md border p-3 text-sm ${days < 0 ? "border-destructive/40 text-destructive" : "border-border"}`}
    >
      <p className="font-medium">{message}</p>
      <p className="text-text-muted">{t.deadlineDate.replace("{date}", formatDate(limit))}</p>
    </div>
  );
}

function DraftBody({ draft }: { draft: RapportProvisoire }) {
  const responses = useDraftResponses({ provisoire: draft.id });
  const [target, setTarget] = useState<ConstatProvisoire | null>(null);

  if (responses.isError) {
    return (
      <div role="alert" className={`${ALERT_CLASS} flex flex-wrap items-center gap-3`}>
        <span>{t.loadError}</span>
        <Button type="button" variant="outline" size="sm" onClick={() => void responses.refetch()}>
          {fr.common.retry}
        </Button>
      </div>
    );
  }
  if (responses.isPending) {
    return (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  }
  const mine = responses.data.results;
  const references = new Map(draft.constats.map((c) => [c.id, c.reference]));

  return (
    <>
      <DeadlineAlert limit={draft.date_limite_reponses} />
      <section aria-labelledby="draft-doc" className="grid gap-2">
        <h3 id="draft-doc" className="text-base font-semibold">
          {t.draftDocumentTitle}
        </h3>
        <DocumentSlot
          typeDocument="RAPPORT_PROVISOIRE"
          objetId={draft.id}
          missionId={draft.mission}
        />
      </section>
      <section aria-labelledby="draft-findings" className="grid gap-2">
        <h3 id="draft-findings" className="text-base font-semibold">
          {t.myFindingsTitle}
        </h3>
        {draft.constats.length === 0 ? (
          <p className="text-sm text-text-muted">{t.myFindingsEmpty}</p>
        ) : (
          <ul className="grid gap-2">
            {draft.constats.map((c) => {
              const answered = mine.some((r) => r.constat === c.id);
              return (
                <li
                  key={c.id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border p-3 text-sm"
                >
                  <span>
                    {c.reference} · {c.titre}
                  </span>
                  {answered ? (
                    <StatusPill label={t.answered} tone="success" />
                  ) : (
                    c.a_repondre && (
                      <Button
                        type="button"
                        size="sm"
                        aria-label={`${t.answer} ${c.reference}`}
                        onClick={() => setTarget(c)}
                      >
                        {t.answer}
                      </Button>
                    )
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>
      <section aria-labelledby="draft-mine" className="grid gap-2">
        <h3 id="draft-mine" className="text-base font-semibold">
          {t.myResponsesTitle}
        </h3>
        {mine.length === 0 ? (
          <p className="text-sm text-text-muted">{t.myResponsesEmpty}</p>
        ) : (
          <ul className="grid gap-2">
            {mine.map((r) => (
              <li key={r.id} className="grid gap-1 rounded-md border border-border p-3 text-sm">
                <span className="flex flex-wrap items-center gap-2 font-medium">
                  {references.get(r.constat) ?? ""} · {formatDateTime(r.confirmation.confirme_le)}
                  {r.hors_delai && <StatusPill label={t.late} tone="warning" />}
                </span>
                <span className="whitespace-pre-line">{r.commentaire}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
      {target && (
        <DraftResponseDialog
          provisoire={draft}
          constat={target}
          open
          onOpenChange={(open) => !open && setTarget(null)}
        />
      )}
    </>
  );
}

/** Réponses de l'audité au rapport provisoire : délai, document, constats de son entité. */
export function ReponsesProvisoirePage() {
  const { id } = useParams();
  const drafts = useMissionDrafts(id);
  const draft = latestDraft(drafts.data?.results ?? []);

  let body;
  if (drafts.isError) {
    body = (
      <div role="alert" className={`${ALERT_CLASS} flex flex-wrap items-center gap-3`}>
        <span>{t.loadError}</span>
        <Button type="button" variant="outline" size="sm" onClick={() => void drafts.refetch()}>
          {fr.common.retry}
        </Button>
      </div>
    );
  } else if (drafts.isPending) {
    body = (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  } else if (!draft) {
    body = <p className="text-sm text-text-muted">{t.noDraft}</p>;
  } else {
    body = <DraftBody draft={draft} />;
  }

  return (
    <section aria-labelledby="reponses-provisoire" className="grid gap-4">
      <h2 id="reponses-provisoire" className="text-lg font-semibold">
        {fr.communication.draftResponsesTitle}
      </h2>
      <p className="text-sm text-text-muted">{t.pageIntro}</p>
      {body}
    </section>
  );
}
