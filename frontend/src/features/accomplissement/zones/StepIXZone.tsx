import { ZoneSkeleton } from "@/features/accomplissement/zones/ZoneSkeleton";
import type { ZoneProps } from "@/features/missions/zones";

/** Étape IX : Fiches de test (zone de travail livrée par les tâches suivantes du lot 6). */
export function StepIXZone({ step }: ZoneProps) {
  return <ZoneSkeleton id={`zone-IX-${step.id}`} title="Fiches de test" />;
}
