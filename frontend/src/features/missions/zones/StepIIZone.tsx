import { Link } from "react-router-dom";
import { fr } from "@/i18n/fr";
import { useDeclarations, useInterviews, useMeetings } from "../api";
import { InterviewTable } from "../components/InterviewTable";
import { MeetingCard } from "../components/MeetingCard";
import type { Etape, Mission } from "../types";

const t = fr.missionTravaux;

/** Étape II : réunion d'ouverture, premiers entretiens et déclarations d'indépendance. */
export function StepIIZone({ mission, step }: { mission: Mission; step: Etape }) {
  const meetings = useMeetings(mission.id);
  const interviews = useInterviews({ mission: mission.id });
  const pending = useDeclarations({ mission: mission.id, statut: "EN_ATTENTE" });

  const upcoming = (interviews.data?.results ?? []).filter(
    (e) => e.etape === step.id || (!e.etape && e.statut === "PLANIFIE"),
  );

  return (
    <div className="grid gap-6">
      <h2 className="text-base font-semibold">
        {step.romain} · {step.titre}
      </h2>

      <MeetingCard
        mission={mission}
        type="OUVERTURE"
        meeting={meetings.data?.results.find((m) => m.type === "OUVERTURE")}
      />

      <section aria-labelledby="step2-interviews" className="grid gap-2">
        <h3 id="step2-interviews" className="text-base font-semibold">
          {t.stepIIInterviews}
        </h3>
        {interviews.isError ? (
          <p role="alert" className="text-sm text-destructive">
            {t.loadError}
          </p>
        ) : (
          <InterviewTable mission={mission} interviews={upcoming} label={t.stepIIInterviews} />
        )}
      </section>

      <section aria-labelledby="step2-declarations" className="grid gap-2">
        <h3 id="step2-declarations" className="text-base font-semibold">
          {t.declarationsTitle}
        </h3>
        {pending.data && (
          <p className="text-sm" role="status">
            {pending.data.count > 0
              ? t.declarationsPending.replace("{count}", String(pending.data.count))
              : t.declarationsDone}
          </p>
        )}
        <Link
          to={`/missions/${mission.id}/equipe`}
          className="text-sm text-primary underline underline-offset-2"
        >
          {t.declarationsLink}
        </Link>
      </section>
      {/* LOT4-SLOT: documents de l'étape II (ordre de mission, convocations). */}
    </div>
  );
}
