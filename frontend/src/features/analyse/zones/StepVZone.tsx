import { ALERT_CLASS } from "@/components/form/FormField";
import type { ZoneProps } from "@/features/missions/zones";
import { fr } from "@/i18n/fr";
import { useAuditFramework } from "../api";
import { MarcTable } from "../components/MarcTable";
import { QciSection } from "../components/QciSection";
import { StrengthsWeaknessesTable } from "../components/StrengthsWeaknessesTable";

const t = fr.analyseVVI;

/** Étape V : QCI, matrice des risques et contrôles, forces et faiblesses. Écriture si `contribuer_v`. */
export function StepVZone({ mission, step }: ZoneProps) {
  const framework = useAuditFramework(mission.id);
  const id = `analyse-v-${step.id}`;

  if (framework.isError) {
    return (
      <p role="alert" className={ALERT_CLASS}>
        {t.loadError}
      </p>
    );
  }
  if (framework.isPending) {
    return (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  }
  const editable = framework.data.mes_droits.contribuer_v;

  return (
    <section aria-labelledby={id} className="grid gap-6">
      <h3 id={id} className="text-base font-semibold">
        {t.stepVTitle}
      </h3>
      <QciSection mission={mission} editable={editable} />
      <MarcTable missionId={mission.id} editable={editable} level={4} />
      <StrengthsWeaknessesTable missionId={mission.id} editable={editable} level={4} />
    </section>
  );
}
