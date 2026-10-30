import { ZoneSkeleton } from "@/features/accomplissement/zones/ZoneSkeleton";
import type { ZoneProps } from "@/features/missions/zones";
import { fr } from "@/i18n/fr";

/** Étape XV : rapport provisoire et réponses des audités (squelette ; contenu : T13). */
export function StepXVZone({ step }: ZoneProps) {
  return <ZoneSkeleton id={`zone-XV-${step.id}`} title={fr.communication.zoneXVTitle} />;
}
