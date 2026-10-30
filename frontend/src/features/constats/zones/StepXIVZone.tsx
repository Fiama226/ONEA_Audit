import { ZoneSkeleton } from "@/features/accomplissement/zones/ZoneSkeleton";
import type { ZoneProps } from "@/features/missions/zones";

/** Étape XIV : Constats (zone de travail livrée par les tâches suivantes du lot 6). */
export function StepXIVZone({ step }: ZoneProps) {
  return <ZoneSkeleton id={`zone-XIV-${step.id}`} title="Constats" />;
}
