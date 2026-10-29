import { useState } from "react";
import { isApiError } from "@/api/errors";
import { ALERT_CLASS } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import type { ZoneProps } from "@/features/missions/zones";
import { fr } from "@/i18n/fr";
import {
  useAuditFramework,
  useProcessDescriptions,
  useQuestionnaires,
  useSaveQuestionnaire,
  useSegregationGrids,
} from "../api";
import { ProcessDescriptionForm } from "../components/ProcessDescriptionForm";
import { QciSection } from "../components/QciSection";
import { QuestionnaireEditor } from "../components/QuestionnaireEditor";
import { SegregationGridEditor } from "../components/SegregationGridEditor";

const t = fr.analyse;
const a = fr.analyseIII;

/** Complément de l'étape III : prise de connaissance, description des processus, grilles, QCI. */
export function StepIIIAnalyse({ mission, step }: ZoneProps) {
  const id = `analyse-${step.id}`;
  const framework = useAuditFramework(mission.id);
  const questionnaires = useQuestionnaires(mission.id, "PRISE_CONNAISSANCE");
  const descriptions = useProcessDescriptions(mission.id);
  const grids = useSegregationGrids(mission.id);
  const create = useSaveQuestionnaire();
  const [createError, setCreateError] = useState<string | null>(null);

  const queries = [framework, questionnaires, descriptions, grids];
  const failed = queries.find((q) => q.isError);
  const loading = queries.some((q) => q.isPending);
  // D16 : les droits viennent du serveur, jamais recalculés ici.
  const editable = framework.data?.mes_droits.contribuer_iii ?? false;

  async function createQuestionnaire() {
    setCreateError(null);
    try {
      await create.mutateAsync({ data: { mission: mission.id, type: "PRISE_CONNAISSANCE" } });
    } catch (e) {
      setCreateError(isApiError(e) ? e.detail : fr.errors.generic);
    }
  }

  let body;
  if (failed) {
    body = (
      <div role="alert" className={ALERT_CLASS}>
        <p>{a.loadError}</p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => void Promise.all(queries.filter((q) => q.isError).map((q) => q.refetch()))}
        >
          {fr.common.retry}
        </Button>
      </div>
    );
  } else if (loading) {
    body = (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  } else {
    const questionnaire = questionnaires.data?.results[0];
    body = (
      <>
        <section aria-labelledby={`${id}-q`} className="grid gap-3">
          <h4 id={`${id}-q`} className="text-base font-semibold">
            {a.questionnaireTitle}
          </h4>
          {questionnaire ? (
            <QuestionnaireEditor
              questionnaire={questionnaire}
              editable={editable}
              missionReference={mission.reference}
            />
          ) : (
            <div className="flex flex-wrap items-center gap-3">
              <p className="text-sm text-text-muted">{a.noQuestionnaire}</p>
              {editable && (
                <Button
                  type="button"
                  size="sm"
                  disabled={create.isPending}
                  onClick={() => void createQuestionnaire()}
                >
                  {a.createQuestionnaire}
                </Button>
              )}
            </div>
          )}
          {createError && (
            <p role="alert" className="text-sm text-destructive">
              {createError}
            </p>
          )}
        </section>

        <section aria-labelledby={`${id}-p`} className="grid gap-3">
          <h4 id={`${id}-p`} className="text-base font-semibold">
            {a.processesTitle}
          </h4>
          {mission.processus_detail.length === 0 ? (
            <p className="text-sm text-text-muted">{a.noProcess}</p>
          ) : (
            mission.processus_detail.map((p) => (
              <ProcessDescriptionForm
                key={p.id}
                mission={mission}
                processus={p}
                description={descriptions.data?.results.find((d) => d.processus === p.id)}
                editable={editable}
              />
            ))
          )}
          <p className="text-sm text-text-muted">{a.flowNote}</p>
        </section>

        <section aria-labelledby={`${id}-g`} className="grid gap-3">
          <h4 id={`${id}-g`} className="text-base font-semibold">
            {a.gridsTitle}
          </h4>
          <p className="text-sm text-text-muted">{a.gridsHelp}</p>
          {mission.processus_detail.map((p) => (
            <SegregationGridEditor
              key={p.id}
              mission={mission}
              processus={p}
              grid={grids.data?.results.find((g) => g.processus === p.id)}
              editable={editable}
            />
          ))}
        </section>

        <QciSection mission={mission} editable={editable} />
      </>
    );
  }

  return (
    <section aria-labelledby={id} className="grid gap-6">
      <h3 id={id} className="text-base font-semibold">
        {t.stepIIITitle}
      </h3>
      {body}
    </section>
  );
}
