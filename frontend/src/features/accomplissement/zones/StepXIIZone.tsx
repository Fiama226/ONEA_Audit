import { ZoneSkeleton } from "@/features/accomplissement/zones/ZoneSkeleton";
import type { ZoneProps } from "@/features/missions/zones";

/** Étape XII : Tests complémentaires (zone de travail livrée par les tâches suivantes du lot 6). */
export function StepXIIZone({ step }: ZoneProps) {
  return <ZoneSkeleton id={`zone-XII-${step.id}`} title="Tests complémentaires" />;
}
