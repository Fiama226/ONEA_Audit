import { Link } from "react-router-dom";
import { ALERT_CLASS } from "@/components/form/FormField";
import type { ZoneProps } from "@/features/missions/zones";
import { fr } from "@/i18n/fr";
import { useAuditFramework } from "../api";
import { FrameworkStatusPanel } from "../components/FrameworkStatusPanel";

const t = fr.analyseVVI;

/** Étape VI : état du référentiel d'audit ; les jalons restent portés par `StepActions`. */
export function StepVIZone({ mission, step }: ZoneProps) {
  const framework = useAuditFramework(mission.id);
  const id = `analyse-vi-${step.id}`;

  return (
    <section aria-labelledby={id} className="grid gap-4">
      <h3 id={id} className="text-base font-semibold">
        {t.stepVITitle}
      </h3>
      {framework.isError && (
        <p role="alert" className={ALERT_CLASS}>
          {t.loadError}
        </p>
      )}
      {framework.isPending && (
        <p role="status" className="text-sm text-text-muted">
          {fr.common.loading}
        </p>
      )}
      {framework.data && <FrameworkStatusPanel framework={framework.data} />}
      <p className="text-sm">{t.stepVIReminder}</p>
      <p>
        <Link
          to={`/missions/${mission.id}/referentiel-audit`}
          className="text-sm font-medium text-primary underline underline-offset-2"
        >
          {t.openFramework}
        </Link>
      </p>
    </section>
  );
}
