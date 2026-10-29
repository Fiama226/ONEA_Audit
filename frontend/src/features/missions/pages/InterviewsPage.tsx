import { useState } from "react";
import { useParams } from "react-router-dom";
import { useRole } from "@/auth/useRole";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import { useInterviews, useMission } from "../api";
import { InterviewFormDialog } from "../components/InterviewFormDialog";
import { InterviewTable } from "../components/InterviewTable";

const t = fr.missionTravaux;

/** Entretiens de la mission. L'audité ne voit que les siens (filtrage serveur), sans action. */
export function InterviewsPage() {
  const { id } = useParams();
  const mission = useMission(id);
  const interviews = useInterviews({ mission: id });
  const { is } = useRole();
  const [creating, setCreating] = useState(false);

  if (interviews.isError) {
    return (
      <p role="alert" className="text-sm text-destructive">
        {t.loadError}
      </p>
    );
  }
  if (!mission.data || !interviews.data) {
    return (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  }
  const data = mission.data;

  return (
    <section aria-labelledby="interviews-title" className="grid gap-4">
      <div className="hidden print:block">
        <h1 className="text-xl font-semibold">{t.planningTitle}</h1>
        <p className="text-sm">
          {t.planningHeader.replace("{reference}", data.reference).replace("{title}", data.titre)}
        </p>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 print:hidden">
        <h2 id="interviews-title" className="text-lg font-semibold">
          {t.interviewsTitle}
        </h2>
        <div className="flex gap-2">
          {!is("AUDITE") && (
            <Button type="button" variant="outline" onClick={() => window.print()}>
              {t.printPlanning}
            </Button>
          )}
          {data.mes_droits.contribuer && (
            <Button type="button" onClick={() => setCreating(true)}>
              {t.planInterview}
            </Button>
          )}
        </div>
      </div>
      <InterviewTable
        mission={data}
        interviews={interviews.data.results}
        filterable
        label={t.interviewsTitle}
      />
      {data.mes_droits.contribuer && creating && (
        <InterviewFormDialog open onOpenChange={setCreating} mission={data} />
      )}
    </section>
  );
}
