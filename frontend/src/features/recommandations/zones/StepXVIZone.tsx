import type { ZoneProps } from "@/features/missions/zones";
import { fr } from "@/i18n/fr";
import { PlanActionsContent } from "../pages/PlanActionsPage";

/** Étape XVI : plan d'actions de la mission ; les actions de l'étape sont portées par `StepPage`. */
export function StepXVIZone({ mission, step }: ZoneProps) {
  const id = `zone-XVI-${step.id}`;
  return (
    <section aria-labelledby={id} className="grid gap-4">
      <h3 id={id} className="text-base font-semibold">
        {fr.communication.zoneXVITitle}
      </h3>
      <PlanActionsContent mission={mission} step={step} />
    </section>
  );
}
