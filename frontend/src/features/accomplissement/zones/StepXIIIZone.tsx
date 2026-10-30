import { ZoneSkeleton } from "@/features/accomplissement/zones/ZoneSkeleton";
import type { ZoneProps } from "@/features/missions/zones";

/** Étape XIII : Validation des fiches (zone de travail livrée par les tâches suivantes du lot 6). */
export function StepXIIIZone({ step }: ZoneProps) {
  return <ZoneSkeleton id={`zone-XIII-${step.id}`} title="Validation des fiches" />;
}
