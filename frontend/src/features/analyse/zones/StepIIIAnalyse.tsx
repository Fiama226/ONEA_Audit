import { fr } from "@/i18n/fr";
import type { ZoneProps } from "@/features/missions/zones";
import { QciSection } from "../components/QciSection";

const t = fr.analyse;

/** Complément de l'étape III : prise de connaissance, processus, QCI (squelette, lot 5 T9). */
export function StepIIIAnalyse({ mission, step }: ZoneProps) {
  const id = `analyse-${step.id}`;
  return (
    <section aria-labelledby={id} className="grid gap-4">
      <h3 id={id} className="text-base font-semibold">
        {t.stepIIITitle}
      </h3>
      <QciSection mission={mission} editable={mission.mes_droits.voir_travaux} />
    </section>
  );
}
