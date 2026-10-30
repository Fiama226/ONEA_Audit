import { ZoneSkeleton } from "@/features/accomplissement/zones/ZoneSkeleton";
import type { ZoneProps } from "@/features/missions/zones";

/** Étape VIII : Programme de travail (zone de travail livrée par les tâches suivantes du lot 6). */
export function StepVIIIZone({ step }: ZoneProps) {
  return <ZoneSkeleton id={`zone-VIII-${step.id}`} title="Programme de travail" />;
}
