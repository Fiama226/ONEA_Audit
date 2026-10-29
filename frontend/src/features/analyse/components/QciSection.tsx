import { useState } from "react";
import { ALERT_CLASS } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import type { Mission } from "@/features/missions/types";
import { fr } from "@/i18n/fr";
import { isApiError } from "@/api/errors";
import { useQuestionnaires, useSaveQuestionnaire } from "../api";
import { QuestionnaireEditor } from "./QuestionnaireEditor";

const t = fr.analyseIII;

export type QciSectionProps = { mission: Mission; editable: boolean };

/** Un questionnaire de contrôle interne par processus de la mission. */
export function QciSection({ mission, editable }: QciSectionProps) {
  const qcis = useQuestionnaires(mission.id, "QCI");
  const create = useSaveQuestionnaire();
  const [error, setError] = useState<string | null>(null);

  async function createFor(processus: string) {
    setError(null);
    try {
      await create.mutateAsync({ data: { mission: mission.id, type: "QCI", processus } });
    } catch (e) {
      setError(isApiError(e) ? e.detail : fr.errors.generic);
    }
  }

  return (
    <section aria-labelledby={`qci-${mission.id}`} className="grid gap-3">
      <h4 id={`qci-${mission.id}`} className="text-base font-semibold">
        {t.qciTitle}
      </h4>
      {qcis.isPending ? (
        <p role="status" className="text-sm text-text-muted">
          {fr.common.loading}
        </p>
      ) : qcis.isError ? (
        <div role="alert" className={ALERT_CLASS}>
          <p>{t.loadError}</p>
          <Button type="button" variant="outline" size="sm" onClick={() => void qcis.refetch()}>
            {fr.common.retry}
          </Button>
        </div>
      ) : mission.processus_detail.length === 0 ? (
        <p className="text-sm text-text-muted">{t.noProcess}</p>
      ) : (
        mission.processus_detail.map((p) => {
          const qci = qcis.data.results.find((q) => q.processus === p.id);
          const title = t.qciProcess.replace("{process}", `${p.code} — ${p.libelle}`);
          return (
            <div key={p.id} className="grid gap-3 rounded-md border border-border p-4">
              <h5 className="text-sm font-semibold">{title}</h5>
              {qci ? (
                <QuestionnaireEditor
                  questionnaire={qci}
                  editable={editable}
                  missionReference={mission.reference}
                />
              ) : (
                <div className="flex flex-wrap items-center gap-3">
                  <p className="text-sm text-text-muted">{t.noQuestionnaire}</p>
                  {editable && (
                    <Button
                      type="button"
                      size="sm"
                      className="print:hidden"
                      aria-label={`${t.createQci} : ${p.code}`}
                      disabled={create.isPending}
                      onClick={() => void createFor(p.id)}
                    >
                      {t.createQci}
                    </Button>
                  )}
                </div>
              )}
            </div>
          );
        })
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
    </section>
  );
}
