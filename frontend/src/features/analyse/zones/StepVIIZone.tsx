import { ALERT_CLASS } from "@/components/form/FormField";
import type { ZoneProps } from "@/features/missions/zones";
import { fr } from "@/i18n/fr";
import { useAuditFramework } from "../api";
import { ObjectivesTable } from "../components/ObjectivesTable";
import { OrientationReportForm } from "../components/OrientationReportForm";

const t = fr.analyseVII;

/** Étape VII : objectifs d'audit et rapport d'orientation (droits du serveur, D16). */
export function StepVIIZone({ mission, step }: ZoneProps) {
  const framework = useAuditFramework(mission.id);
  const id = `analyse-vii-${step.id}`;

  let body;
  if (framework.isPending) {
    body = <p role="status">{t.loading}</p>;
  } else if (framework.isError) {
    body = (
      <p role="alert" className={ALERT_CLASS}>
        {fr.analyse.loadError}
      </p>
    );
  } else if (framework.data.statut !== "VALIDE") {
    body = (
      <p role="alert" className="rounded-md border border-border p-3 text-sm">
        {t.frameworkRequired}
      </p>
    );
  } else {
    const editable = framework.data.mes_droits.contribuer_vii;
    body = (
      <>
        <ObjectivesTable missionId={mission.id} editable={editable} />
        <OrientationReportForm missionId={mission.id} editable={editable} />
        <p className="text-sm text-text-muted">{t.wordNote}</p>
      </>
    );
  }

  return (
    <section aria-labelledby={id} className="grid gap-4">
      <h3 id={id} className="text-base font-semibold">
        {t.title}
      </h3>
      {body}
    </section>
  );
}
