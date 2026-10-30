import { ZoneSkeleton } from "@/features/accomplissement/zones/ZoneSkeleton";
import type { ZoneProps } from "@/features/missions/zones";

/** Étape X : Validation des preuves (zone de travail livrée par les tâches suivantes du lot 6). */
export function StepXZone({ step }: ZoneProps) {
  return <ZoneSkeleton id={`zone-X-${step.id}`} title="Validation des preuves" />;
}
