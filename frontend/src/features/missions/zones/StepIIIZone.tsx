import { fr } from "@/i18n/fr";
import { useInterviews } from "../api";
import { InterviewTable } from "../components/InterviewTable";
import type { Etape, Mission } from "../types";

const t = fr.missionTravaux;

/** Étape III : entretiens rattachés à l'étape (le questionnaire et les processus viennent au lot 5). */
export function StepIIIZone({ mission, step }: { mission: Mission; step: Etape }) {
  const interviews = useInterviews({ mission: mission.id, etape: step.id });

  return (
    <div className="grid gap-6">
      <h2 className="text-base font-semibold">
        {step.romain} · {step.titre}
      </h2>
      <section aria-labelledby="step3-interviews" className="grid gap-2">
        <h3 id="step3-interviews" className="text-base font-semibold">
          {t.stepIIIInterviews} {step.romain}
        </h3>
        {interviews.isError ? (
          <p role="alert" className="text-sm text-destructive">
            {t.loadError}
          </p>
        ) : (
          <InterviewTable
            mission={mission}
            interviews={interviews.data?.results ?? []}
            label={`${t.stepIIIInterviews} ${step.romain}`}
          />
        )}
      </section>
      {/* LOT5-SLOT: questionnaire de prise de connaissance et description des processus. */}
      <p className="text-sm text-text-muted">{t.stepIIILater}</p>
    </div>
  );
}
