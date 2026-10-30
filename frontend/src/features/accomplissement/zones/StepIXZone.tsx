import { ALERT_CLASS } from "@/components/form/FormField";
import type { ZoneProps } from "@/features/missions/zones";
import { fr } from "@/i18n/fr";
import { usePlannedTests, useWorkPrograms } from "../api";
import { ProgramSummary } from "../components/ProgramSummary";
import { ResourcesTable } from "../components/ResourcesTable";

const t = fr.programme;

/** Étape IX : ressources du programme (auditeurs, charges, dates) et synthèse. */
export function StepIXZone({ mission, step }: ZoneProps) {
  const programs = useWorkPrograms(mission.id);
  const tests = usePlannedTests({ mission: mission.id });
  const id = `zone-IX-${step.id}`;

  let body;
  if (programs.isPending || tests.isPending) {
    body = (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  } else if (programs.isError || tests.isError) {
    body = (
      <p role="alert" className={ALERT_CLASS}>
        {t.loadError}
      </p>
    );
  } else {
    const editable = programs.data.results.some((p) =>
      p.actions_possibles.includes("MODIFIER_RESSOURCES"),
    );
    body = (
      <>
        <p className="text-sm text-text-muted">{t.resourcesIntro}</p>
        <ResourcesTable
          missionId={mission.id}
          equipe={mission.equipe}
          tests={tests.data.results}
          editable={editable}
        />
      </>
    );
  }

  return (
    <section aria-labelledby={id} className="grid gap-4">
      <h3 id={id} className="text-base font-semibold">
        {t.resourcesTitle}
      </h3>
      {body}
      <ProgramSummary missionId={mission.id} />
    </section>
  );
}
