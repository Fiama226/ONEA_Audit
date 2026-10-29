import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ALERT_CLASS } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import { useDeclarations, useInterviews, useMeetings } from "../api";
import { InterviewTable } from "../components/InterviewTable";
import { MeetingCard } from "../components/MeetingCard";
import type { Etape, Mission } from "../types";

const t = fr.missionTravaux;

type QueryLike = { isLoading: boolean; isError: boolean; refetch: () => unknown };

/** Chargement ou erreur (avec « Réessayer ») ; sinon le contenu, jamais un état vide trompeur. */
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
  if (query.isLoading) {
    return (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  }
  return <>{children}</>;
}

/** Étape II : réunion d'ouverture, premiers entretiens et déclarations d'indépendance. */
export function StepIIZone({ mission, step }: { mission: Mission; step: Etape }) {
  const meetings = useMeetings(mission.id);
  const interviews = useInterviews({ mission: mission.id });
  const declarations = useDeclarations({ mission: mission.id });

  const upcoming = (interviews.data?.results ?? []).filter(
    (e) => e.etape === step.id || (!e.etape && e.statut === "PLANIFIE"),
  );
  // Même règle que le serveur : une déclaration est « levée » si elle est confirmée, ou si le
  // conflit déclaré a été arbitré. Le champ `levee` vient du serveur.
  const unresolved = (declarations.data?.results ?? []).filter((d) => !d.levee).length;
  const stepClosed = step.statut === "VALIDEE" || step.statut === "NON_APPLICABLE";

  return (
    <div className="grid gap-6">
      <h2 className="text-base font-semibold">
        {step.romain} · {step.titre}
      </h2>

      <Loaded query={meetings}>
        <MeetingCard
          mission={mission}
          type="OUVERTURE"
          meeting={meetings.data?.results.find((m) => m.type === "OUVERTURE")}
          stepClosed={stepClosed}
        />
      </Loaded>

      <section aria-labelledby="step2-interviews" className="grid gap-2">
        <h3 id="step2-interviews" className="text-base font-semibold">
          {t.stepIIInterviews}
        </h3>
        <Loaded query={interviews}>
          <InterviewTable mission={mission} interviews={upcoming} label={t.stepIIInterviews} />
        </Loaded>
      </section>

      <section aria-labelledby="step2-declarations" className="grid gap-2">
        <h3 id="step2-declarations" className="text-base font-semibold">
          {t.declarationsTitle}
        </h3>
        <Loaded query={declarations}>
          <p className="text-sm" role="status">
            {unresolved > 0
              ? t.declarationsPending.replace("{count}", String(unresolved))
              : t.declarationsDone}
          </p>
        </Loaded>
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
